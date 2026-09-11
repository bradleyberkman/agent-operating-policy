# Codex surface notes

## Codex CLI

The selected repository may expose `AGENTS.md`, repository skills, local-root skills, system skills, symlinks, plugin configuration, provider-qualified fresh-session receipts, hooks, MCP/app tools, permissions, tests, and version-control state. Treat each as a separate observed control and use only the roots explicitly in scope.

- Local configuration proves configured state, not session exposure.
- A fresh session receipt proves exposure for that session, not invocation.
- A minimal invocation receipt proves a named caller reached a provider-qualified callable, not usefulness or acceptance.
- Account-provided plugins may not appear in local configuration; report that mismatch rather than inventing an owner.
- Hidden routing, provider state, account memory, and unexposed tool selection remain `INACCESSIBLE`.

## Codex app

Inspect only the workspace, attachments, settings, plugins, apps, and receipts the current app surface exposes. Do not infer that another workspace, chat, or account-level control is visible merely because the host can access a related path.

## OpenAI API

Inspect only the request-time instructions, tools, schemas, middleware, and traces supplied to the audit. Vendor-side routing and retained state are `INACCESSIBLE` unless a first-party receipt exposes them.
