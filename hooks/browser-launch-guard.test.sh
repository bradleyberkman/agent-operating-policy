#!/usr/bin/env bash
# Failure protected: a Claude Code Bash call must not start an unmanaged browser or
# attach to the operator's personal Chrome state while still allowing reviewed,
# headless Playwright suites and browser diagnostics.
# Owner: this source-unit proof owns the Claude raw-launch decision matrix; the
# policy rendering and generated-path checks own only their respective wiring.
# Retire when: Claude provides a tested, centrally enforced session capability
# policy that distinguishes attended personal-Chrome use from managed runners.

set -uo pipefail

GUARD="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/browser-launch-guard.sh"
FAILURES=0

ok() { printf '  ok   %s\n' "$1"; }
fail() {
  printf '  FAIL %s\n       %s\n' "$1" "$2"
  FAILURES=$((FAILURES + 1))
}

run_hook() {
  python3 -c '
import json, sys
print(json.dumps({"tool_name": sys.argv[1], "tool_input": {"command": sys.argv[2]}}))
' "$1" "$2" | bash "$GUARD"
}

denied() { grep -q '"permissionDecision": "deny"' <<<"$1"; }

CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

while IFS= read -r command; do
  [ -n "$command" ] || continue
  output=$(run_hook Bash "$command")
  if denied "$output"; then
    ok "denied unmanaged launch: $command"
  else
    fail "denied unmanaged launch: $command" "$output"
  fi
done <<COMMANDS
$CHROME --headless=new --remote-debugging-port=9222 --user-data-dir=/tmp/browser-profile about:blank
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --headless=new about:blank
nohup "$CHROME" --headless=new --user-data-dir=/tmp/browser-profile about:blank >/tmp/browser.log 2>&1 &
bash -lc 'google-chrome --headless=new about:blank'
FOO=bar google-chrome --headless=new about:blank
if true; then google-chrome --headless=new about:blank; fi
eval 'google-chrome --headless=new about:blank'
bash -lc 'open https://example.com'
open -a "Google Chrome" https://example.com
open -b com.google.Chrome http://localhost:3000
open https://example.com
npx playwright codegen https://example.com
npx playwright screenshot https://example.com /tmp/page.png
npx playwright test --headed
npx playwright test --ui
npx playwright test --debug
PWDEBUG=1 npx playwright test
pnpm playwright test --ui
npm exec playwright test --ui
./node_modules/.bin/playwright test --debug
node -e "require('playwright').chromium.launch({headless:true})"
python3 -c "from playwright.sync_api import sync_playwright; sync_playwright().start().chromium.launch()"
python3 /tmp/ad-hoc-playwright.py
COMMANDS

while IFS= read -r command; do
  [ -n "$command" ] || continue
  output=$(run_hook Bash "$command")
  if denied "$output"; then
    fail "allowed managed or diagnostic command: $command" "$output"
  else
    ok "allowed: $command"
  fi
done <<'COMMANDS'
npx playwright test
pnpm exec playwright test tests/browser.spec.ts
npm run test:e2e
node tools/verify-local.mjs
npx playwright install chromium
brew install --cask google-chrome
ps aux | grep -i chrome
pgrep -f "Google Chrome"
pkill -f chromium
ls "/Applications/Google Chrome.app"
curl -fsS http://localhost:3000/health
my-cli --headless --user-data-dir=/tmp/not-a-browser
COMMANDS

output=$(run_hook Read "$CHROME --headless --user-data-dir=/tmp/browser-profile")
if denied "$output"; then
  fail "non-Bash tool passes through" "$output"
else
  ok "non-Bash tool passes through"
fi

for malformed in 'not json' ''; do
  output=$(printf '%s' "$malformed" | bash "$GUARD")
  if denied "$output"; then
    fail "malformed payload fails open" "$output"
  else
    ok "malformed payload fails open"
  fi
done

output=$(run_hook Bash "$CHROME --headless --user-data-dir=/tmp/browser-profile")
for phrase in 'managed Playwright' 'harness preview' 'Claude-in-Chrome' 'Operator-present'; do
  if grep -q "$phrase" <<<"$output"; then
    ok "denial explains: $phrase"
  else
    fail "denial explains: $phrase" "$output"
  fi
done

if [[ $FAILURES -gt 0 ]]; then
  printf '\nbrowser-launch-guard spec: %d failure(s)\n' "$FAILURES"
  exit 1
fi
printf '\nbrowser-launch-guard spec: all cases pass\n'
