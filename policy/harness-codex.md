# Codex harness routing

- Repository-local `AGENTS.md` files add only repository-specific routing and constraints.
- Codex uses a managed Playwright runner for durable browser proof and Playwright MCP for bounded exploration. It does not attach to the operator's personal Chrome profile by default.
- The presence of Chrome or Computer Use tools does not authorize them. Use either only for an explicitly requested operator-present attended task; ordinary local verification stays in isolated Playwright state.
