# Claude harness routing

- Repository-local `CLAUDE.md` files add only repository-specific routing and constraints.
- Routine Claude sessions run without personal-Chrome capability; when the launcher exposes the choice, use `--no-chrome`. Use `--chrome` only for an explicitly requested operator-present task that depends on Claude-in-Chrome and end that dedicated session when the attended task is done.
- A Bash PreToolUse guard is a backstop against unmanaged browser launches. It does not turn a harness preview pane into an agent browser and does not replace session-level capability selection.
