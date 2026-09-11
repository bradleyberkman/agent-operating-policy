#!/usr/bin/env bash
# browser-launch-guard.sh — Claude Code PreToolUse guard for unmanaged Bash browsers.
#
# The approved shell path is a checked-in Playwright test or runner. Direct
# browser binaries, `open` URLs, headed Playwright CLI modes, and inline
# Playwright/Puppeteer launch snippets are unmanaged: they can select the operator's
# default profile, create visible windows, or outlive the agent session.
#
# This guard intentionally fails open on malformed hook input or a missing
# Python runtime. A broken hook must not disable every Bash call; process
# cleanup remains a separate backstop. The durable decision matrix lives in
# browser-launch-guard.test.sh.

INPUT=$(cat)
command -v python3 >/dev/null 2>&1 || exit 0

python3 - "$INPUT" <<'PY'
import json
import os
import re
import shlex
import subprocess
import sys

try:
    payload = json.loads(sys.argv[1])
    if payload.get("tool_name") != "Bash":
        raise SystemExit(0)
    command = (payload.get("tool_input") or {}).get("command") or ""
except Exception:
    raise SystemExit(0)

if not command:
    raise SystemExit(0)

# Shell-escaped whitespace is part of the executable token, not a meaningful
# difference in the path. Normalize it only for classification; the original
# command is never evaluated by this hook.
scan_command = re.sub(r"\\([ \t])", r"\1", command)

boundary = r"(?:^|[;&|()\n]\s*)"
assignments = r"(?:(?:[A-Za-z_][A-Za-z0-9_]*=\S+)\s+)*"
wrapper = r"(?:(?:nohup|command|exec|setsid)\s+|sudo(?:\s+-\S+)*\s+)*"
safe_browser_reference = re.compile(
    r"^\s*(?:"
    r"npx\s+playwright\s+install\s+(?:chromium|chrome)|"
    r"brew\s+install\s+--cask\s+(?:google-chrome|chromium|firefox)|"
    r"ps\s+aux\s*\|\s*grep\s+-i\s+(?:chrome|chromium|firefox)|"
    r"pgrep\s+-f\s+[\"']?(?:google chrome|chromium|firefox)[\"']?|"
    r"pkill\s+-f\s+[\"']?(?:google chrome|chromium|firefox)[\"']?|"
    r"ls\s+[\"']?/Applications/(?:Google Chrome|Chromium|Firefox)\.app[\"']?"
    r")\s*$",
    re.IGNORECASE,
)
if safe_browser_reference.fullmatch(scan_command):
    raise SystemExit(0)

browser_binary = re.compile(
    r"(?:^|[\s;&|()\"'])(?:[^\"';&|\s]*/)?(?:google(?:\s+|-)chrome|chromium|chrome\.exe|"
      r"microsoft(?:\s+|-)edge|msedge|brave(?:\s+|-)browser|firefox|safari)"
    + r"(?=[\"'\s;&|()]|$)",
    re.IGNORECASE,
)
mac_open = re.compile(
    boundary
    + wrapper
    + r"(?:/usr/bin/)?open\s+(?:(?:-[aAb]\s+[^;&|\n]*(?:chrome|chromium|"
      r"edge|brave|firefox|safari))|(?:https?|file)://)",
    re.IGNORECASE,
)
playwright_cli = re.compile(
    boundary
    + wrapper
    + r"(?:(?:npx|bunx|yarn\s+dlx|pnpm(?:\s+(?:dlx|exec))?|npm\s+exec)\s+)?"
      r"(?:\./)?(?:node_modules/\.bin/)?playwright\s+(?:codegen|screenshot|pdf|open)(?:\s|$)",
    re.IGNORECASE,
)
interactive_test = re.compile(
    boundary
    + assignments
    + wrapper
    + r"(?:(?:npx|bunx|yarn\s+dlx|pnpm(?:\s+(?:dlx|exec))?|npm\s+exec)\s+)?"
      r"(?:\./)?(?:node_modules/\.bin/)?playwright\s+test\b[^;&|\n]*--(?:headed|ui|debug)\b",
    re.IGNORECASE,
)
pwdebug_test = re.compile(
    r"(?:^|[\s;&|()])PWDEBUG\s*=\s*\S+[^;&|\n]*"
    r"(?:(?:npx|bunx|yarn\s+dlx|pnpm(?:\s+(?:dlx|exec))?|npm\s+exec)\s+)?"
    r"(?:\./)?(?:node_modules/\.bin/)?playwright\s+test\b",
    re.IGNORECASE,
)
inline_launch = re.compile(
    boundary
    + r"(?:node|python3?|ruby)\s+(?:-e|-c)\s+[^|\n]*"
      r"(?:playwright|puppeteer|sync_playwright)[^|\n]*\.launch\s*\(",
    re.IGNORECASE,
)
applescript_browser = re.compile(
    boundary
    + wrapper
    + r"osascript\b[^;&|\n]*(?:google chrome|chromium|safari|firefox|brave|edge)",
    re.IGNORECASE,
)
nested_shell = re.compile(
    boundary
    + assignments
    + wrapper
    + r"(?:bash|zsh|sh)\s+-[A-Za-z]*c\s+[\"'][^\n]*"
      r"(?:open\s+(?:https?|file)://|playwright\s+(?:codegen|screenshot|pdf|open)|"
      r"(?:google(?:\s+|-)chrome|chromium|chrome\.exe|microsoft(?:\s+|-)edge|"
      r"msedge|brave(?:\s+|-)browser|firefox|safari)(?=[\"'\s]|$))",
    re.IGNORECASE,
)


def untracked_browser_script(shell_command: str, cwd: str | None) -> bool:
    """Refuse obvious ad-hoc browser runners while allowing tracked runners."""
    try:
        words = shlex.split(shell_command)
    except ValueError:
        return False
    while words and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", words[0]):
        words.pop(0)
    while words and words[0] in {"nohup", "command", "exec", "setsid"}:
        words.pop(0)
    if not words or os.path.basename(words[0]) not in {"node", "python", "python3", "ruby"}:
        return False
    script = next((word for word in words[1:] if not word.startswith("-")), None)
    if not script or not re.search(r"(?:playwright|puppeteer|browser)", script, re.IGNORECASE):
        return False
    if not cwd:
        return True
    candidate = os.path.realpath(script if os.path.isabs(script) else os.path.join(cwd, script))
    root = os.path.realpath(cwd)
    try:
        relative = os.path.relpath(candidate, root)
    except ValueError:
        return True
    if relative == ".." or relative.startswith(".." + os.sep):
        return True
    tracked = subprocess.run(
        ["git", "-C", root, "ls-files", "--error-unmatch", "--", relative],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return tracked.returncode != 0

matched = next(
    (
        label
        for label, pattern in (
            ("direct browser binary", browser_binary),
            ("macOS open-to-browser", mac_open),
            ("standalone Playwright browser command", playwright_cli),
            ("interactive Playwright test", interactive_test),
            ("PWDEBUG Playwright test", pwdebug_test),
            ("inline browser automation launch", inline_launch),
            ("AppleScript browser control", applescript_browser),
            ("nested shell browser launch", nested_shell),
        )
        if pattern.search(scan_command)
    ),
    None,
)

if matched is None and untracked_browser_script(command, payload.get("cwd")):
    matched = "untracked browser runner"

if matched is None:
    raise SystemExit(0)

reason = (
    f"Unmanaged browser launch refused ({matched}).\n\n"
    "Use the route that matches the work:\n"
    "  - Operator-present local review: the operator opens the harness preview and "
    "marks up the page; the preview is not an agent-controlled Chrome profile.\n"
    "  - Unattended local proof: invoke a checked-in managed Playwright test or "
    "runner with an ephemeral context and workspace-scoped artifacts.\n"
    "  - Bounded exploration: use Playwright MCP, then graduate stable assertions "
    "into the checked-in runner.\n"
    "  - Existing personal cookies: only in a dedicated operator-present session "
    "that the operator explicitly asked to run with Claude-in-Chrome.\n\n"
    "Prove the target server answers before navigation. Do not launch a browser "
    "binary, use the default personal profile, or leave a visible browser running "
    "for unattended verification."
)

print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": reason,
}}))
PY
