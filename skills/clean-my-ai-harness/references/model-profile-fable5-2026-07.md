# Dated profile: Fable 5 in Claude.ai

Research cutoff: 2026-07-14

Use this profile only when the selected model is Fable 5 and the target surface is Claude.ai. Claude Code and API use need separate surface notes.

## What the evidence supports

In a bounded three-by-three audit pilot, a compact 742-word execution brief met the requested JSON and word-limit delivery contract in all three runs. A 5,197-word method produced richer analysis but met the delivery contract in one of three runs. The pilot changed method content as well as length. It supports selective loading for that task; it does not prove that short prompts always win or that every old instruction hurts Fable.

## Recommendations to test on the user's setup

- Put the real outcome, facts Fable cannot infer, authority boundary, and finish line at the point of work.
- Let the model choose a route for discovery-heavy work after it sees the evidence.
- Load specialist methods and examples when their phase begins.
- Keep scope, spending, external-action, stopping, and progress-evidence boundaries explicit.
- Move valid JSON, word limits, file existence, and other binary requirements into a validator when the surface supports one. Otherwise run an explicit final check.
- Treat account memory, hidden routing, and vendor-side context as `INACCESSIBLE` unless a surface exposes them.

Label these as dated recommendations, not model personality. Recheck after a major model or Claude.ai runtime change.
