# Exit: Build (spec → implementation)

The classic outcome — but only when it's *genuinely* a build with real architecture choices, and only after
the thinking has actually converged. This is one exit among several, never the default destination.

## Rules

- Reach here only when the user's intent is to ship something and the design forks are settled. Do NOT drag a
  strategy, analysis, or reframe conversation into a spec.
- **Fidelity tracks the phase.** A crisp spec or clean mockup produced mid-divergence is a bug — it anchors the
  user and converges them prematurely. Polish only once convergence is real.
- Prefer the skill/spec file itself as the spec when apt; don't manufacture a separate ceremony doc if a
  lighter artifact captures it.
- Ground the design in the real code (reuse-first: survey existing patterns/files before proposing new).
- Hand execution to the build machinery (a planning skill, an execution skill, or subagents) per the user's control-surface
  rules (e.g. "no direct-to-tree commits until I approve at the end"). The brainstorm skill's terminal act is
  a validated design, not the implementation.
