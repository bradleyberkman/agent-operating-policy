---
name: parallel-web-verification
description: This skill should be used when verifying a local web application, especially a WebGL or Three.js application, from parallel agent workspaces. It defines how to attach to an existing workspace server, bound headless Playwright resources, isolate scenarios with browser contexts, collect deterministic diagnostics, and keep interactive browser use opt-in.
---

# Parallel web verification

Use this skill to verify the application already running for the current
workspace. Keep application-server ownership with the workspace harness and
browser-verification ownership with a bounded local runner.

## Operating contract

- Resolve the target from an explicit URL, `AGENT_VERIFY_URL`, or
  `AGENT_VERIFY_PORT`.
- Attach to the existing server. Do not start a second development server from
  a browser verification command.
- Acquire a bounded verification slot before launching a browser. Use
  `AGENT_VERIFY_SLOTS` to tune the machine-wide limit.
- Launch one headless Chromium process per verification invocation and reuse it
  across the invocation's scenario URLs.
- Create a fresh browser context and page for each scenario URL. Close each
  context before moving to the next scenario.
- Keep user Chrome profiles, visible windows, and interactive MCP sessions out
  of unattended verification.
- Write artifacts to a workspace- and run-scoped output directory. Never use a
  shared screenshot or report filename.

## WebGL lane

For a WebGL smoke check, pass `--require-webgl`. The runner enables SwiftShader
for this deterministic lane and records the WebGL version, vendor, and renderer
in `report.json`. Treat that as a software-rendering smoke result, not as proof
of physical-device GPU fidelity.

Use a separate device or real-GPU walk for motion, shader fidelity, mobile
behavior, accessibility, and final feel. Remote browser services are optional
adapters for compatibility or release matrices; they are not prerequisites for
the local verification contract.

## Runner usage

Run the bundled `scripts/verify.mjs` with a project-local Playwright install or
set `PLAYWRIGHT_MODULE` to the installed Playwright module. Examples:

```bash
node scripts/verify.mjs --url http://127.0.0.1:3000 --screenshot
node scripts/verify.mjs --url http://127.0.0.1:3000 --require-webgl --screenshot
node scripts/verify.mjs \
  --url http://127.0.0.1:3000 \
  --url http://127.0.0.1:3000/index \
  --require-webgl
```

The runner exits nonzero for navigation failures, uncaught page errors, or a
missing required WebGL context. It reports console errors and failed requests
without treating them as failures unless the caller promotes them through its
own policy.

## Parallel-work guidance

Use one application server per independently changing workspace or immutable
build artifact. Reuse that server for all browser scenarios belonging to it.
Do not launch one server or one browser per assertion. Queue work at the
machine-wide verification-slot boundary when multiple agents request checks at
once.

Keep unit tests, type checks, lint, and builds independent of browser startup.
Reserve this skill for a running application, rendered routes, WebGL readiness,
console/runtime diagnostics, and screenshots.
