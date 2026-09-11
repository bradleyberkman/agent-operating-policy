#!/usr/bin/env node

import { createRequire } from 'node:module';
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

function parseArguments(argv) {
  const flags = new Map();
  const urls = [];
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (!argument.startsWith('--')) continue;
    const [key, inlineValue] = argument.slice(2).split('=', 2);
    const value = inlineValue ?? argv[index + 1] ?? 'true';
    if (key === 'url') urls.push(value);
    else flags.set(key, value);
    if (inlineValue === undefined) index += 1;
  }
  return { flags, urls };
}

const { flags, urls: suppliedUrls } = parseArguments(process.argv.slice(2));
const workspacePath = process.env.AGENT_WORKSPACE_PATH ?? process.cwd();
const workspaceName = process.env.AGENT_WORKSPACE_NAME ?? path.basename(workspacePath);
const urls = suppliedUrls.length > 0
  ? suppliedUrls
  : [process.env.AGENT_VERIFY_URL ?? `http://127.0.0.1:${process.env.AGENT_VERIFY_PORT ?? '3000'}`];
const timeout = Number(flags.get('timeout') ?? process.env.AGENT_VERIFY_TIMEOUT_MS ?? 15_000);
const settleMilliseconds = Number(flags.get('settle') ?? process.env.AGENT_VERIFY_SETTLE_MS ?? 250);
const requireWebgl = flags.has('require-webgl') || process.env.AGENT_VERIFY_REQUIRE_WEBGL === '1';
const captureScreenshot = flags.has('screenshot') || process.env.AGENT_VERIFY_SCREENSHOT === '1';
const runId = `${new Date().toISOString().replaceAll(':', '-')}-${process.pid}`;
const outputDir = flags.get('output') ?? process.env.AGENT_VERIFY_OUTPUT ?? path.join(workspacePath, '.context', 'verification', runId);
const slotRoot = process.env.AGENT_VERIFY_SLOT_ROOT ?? path.join(process.env.TMPDIR ?? '/tmp', 'agent-verify-slots');
const maxSlots = Math.max(1, Number(process.env.AGENT_VERIFY_SLOTS ?? 2));
const useSwiftShader = requireWebgl || process.env.AGENT_VERIFY_SWIFTSHADER === '1';

const requireFromCwd = createRequire(path.join(process.cwd(), 'package.json'));
let playwrightModule = process.env.PLAYWRIGHT_MODULE;
if (!playwrightModule) {
  try {
    playwrightModule = requireFromCwd.resolve('playwright');
  } catch {
    throw new Error('Playwright is not available. Install it in the project or set PLAYWRIGHT_MODULE to a Playwright module path.');
  }
}
const { chromium } = await import(playwrightModule);

const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

await mkdir(outputDir, { recursive: true });
await mkdir(slotRoot, { recursive: true });

async function processIsAlive(pid) {
  try {
    process.kill(Number(pid), 0);
    return true;
  } catch {
    return false;
  }
}

async function acquireSlot() {
  while (true) {
    for (let slot = 0; slot < maxSlots; slot += 1) {
      const slotPath = path.join(slotRoot, `slot-${slot}`);
      try {
        await mkdir(slotPath);
        await writeFile(path.join(slotPath, 'owner'), String(process.pid));
        return slotPath;
      } catch (error) {
        if (error.code !== 'EEXIST') throw error;
        try {
          const owner = await readFile(path.join(slotPath, 'owner'), 'utf8');
          if (!(await processIsAlive(owner.trim()))) await rm(slotPath, { recursive: true, force: true });
        } catch {
          // Leave a slot alone while its owner file is being created.
        }
      }
    }
    await sleep(100);
  }
}

async function inspectPage(page) {
  return page.evaluate(() => {
    const canvases = [...document.querySelectorAll('canvas')];
    const canvas = canvases.find((candidate) => candidate.width > 0 && candidate.height > 0) ?? canvases[0];
    let webgl = null;
    if (canvas) {
      const context = canvas.getContext('webgl2') ?? canvas.getContext('webgl') ?? canvas.getContext('experimental-webgl');
      if (context) {
        const debug = context.getExtension('WEBGL_debug_renderer_info');
        webgl = {
          version: context.getParameter(context.VERSION),
          renderer: debug ? context.getParameter(debug.UNMASKED_RENDERER_WEBGL) : null,
          vendor: debug ? context.getParameter(debug.UNMASKED_VENDOR_WEBGL) : null,
        };
      }
    }
    return {
      title: document.title,
      readyState: document.readyState,
      canvasCount: canvases.length,
      webgl,
    };
  });
}

const slotPath = await acquireSlot();
const startedAt = Date.now();
const scenarios = [];
let browser;

try {
  browser = await chromium.launch({
    headless: true,
    args: useSwiftShader ? ['--enable-webgl', '--use-gl=angle', '--use-angle=swiftshader'] : ['--enable-webgl'],
  });

  for (const [index, url] of urls.entries()) {
    const scenario = { url, consoleErrors: [], pageErrors: [], failedRequests: [] };
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    page.on('console', (message) => {
      if (message.type() === 'error') scenario.consoleErrors.push(message.text());
    });
    page.on('pageerror', (error) => scenario.pageErrors.push(String(error)));
    page.on('requestfailed', (request) => scenario.failedRequests.push(`${request.method()} ${request.url()}: ${request.failure()?.errorText ?? 'failed'}`));

    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout });
      await page.waitForLoadState('load', { timeout: Math.min(timeout, 5_000) }).catch(() => {});
      await page.waitForTimeout(settleMilliseconds);
      scenario.probe = await inspectPage(page);
      if (captureScreenshot) await page.screenshot({ path: path.join(outputDir, `page-${index + 1}.png`), fullPage: true });
    } catch (error) {
      scenario.navigationError = String(error);
    } finally {
      await context.close().catch(() => {});
    }
    scenario.ok = !scenario.navigationError && scenario.pageErrors.length === 0 && (!requireWebgl || Boolean(scenario.probe?.webgl));
    scenarios.push(scenario);
  }
} finally {
  await browser?.close().catch(() => {});
  await rm(slotPath, { recursive: true, force: true });
}

const result = {
  ok: scenarios.every((scenario) => scenario.ok),
  workspace: workspaceName,
  durationMs: Date.now() - startedAt,
  outputDir,
  scenarios,
};
await writeFile(path.join(outputDir, 'report.json'), `${JSON.stringify(result, null, 2)}\n`);
console.log(JSON.stringify(result, null, 2));
process.exitCode = result.ok ? 0 : 1;
