# Claude surface notes

## Claude.ai

Claude.ai custom skills can work with content the current conversation, project, connected tools, or code-execution container exposes. They do not automatically reveal every account setting, memory retrieval, project, provider instruction, model route, or fallback.

Use these coverage labels:

- project files or exports opened in the run: `VERIFIED`;
- preferences the user describes but the run cannot inspect: `USER_REPORTED`;
- hidden provider state: `INACCESSIBLE`;
- actual loading during one job: `VERIFIED` only with a trace or receipt.

Approved cleanup produces a revised downloadable copy or bundle. Account-level changes remain a reviewable manual checklist unless the current product exposes a safe settings tool.

## Claude Code

The selected repository may expose more of the harness: `CLAUDE.md`, skills, hooks, settings, permissions, MCP configuration, tools, tests, and version-control state. Map only the chosen root and configuration it inherits. Do not traverse secrets or unrelated home directories.

An instruction that says a reference should load is still `DECLARED` behavior until a trace or receipt proves that it loaded on the sampled job.

## Anthropic API

The API harness can include the caller's system prompt, tool definitions, schemas, model parameters, retrieval, middleware, and validations outside the model call. Ask for or inspect the caller configuration in scope. Do not infer application-side controls from the model response.

## Model identity

Record the exact displayed or configured model and the evidence source. If the product can switch or route models without exposing that event, add it to the blind spots.
