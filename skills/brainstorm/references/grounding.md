# Grounding — what to consult, when, and how deep

Grounding is the base under every mode: open the relevant ground *before* proposing, and import a
genuinely new external bit on every challenge round. This leaf says where to look and how far to go. Grounding
is not always internal — match the source to the topic, and don't assume the topic is the user's own system.

## Match the source to the topic

- **The user's own systems / data / prior decisions** — internal knowledge + live data:
  - The project's knowledge base or wiki search, then read the cited pages in full.
  - The live schema of any database or tracker before reasoning about fields or IDs, and again before any write.
  - Read the actual code / script / firmware / ticket — never reason from a name or from memory.
  - Agent memory and any project context directory for how the user works and project state.
- **General / external / non-project topics, or "what's best-practice / what are others doing"** — web research:
  - Web search and any fetch/crawl tools the harness provides, for current practice, docs, prior art, thinker writing.
  - Prefer primary sources; verify a claim against the canonical source, not a doc that merely cites it.
- **Genuinely greenfield** (no system, no external precedent yet) — reason from first principles and **say so**;
  don't fake a citation.

## When to reach for which

- **Internal first** when the question is about the user's own system, data, or past choices.
- **External** when the challenge needs an outside benchmark (best-practice, prior art, a fact about the
  world), when the topic isn't the user's system at all, or when internal grounding comes up empty.
- **Both** when a build or strategy call should be checked against the existing system *and* outside practice —
  the existing system is evidence, not gospel; best-practice is first-class evidence, not a fallback.

## How deep — scale to the input's weight

- A throwaway musing → a quick check or none; don't over-invest.
- A load-bearing fork or a build/strategy decision → real grounding: read the code, run the query, pull two or
  three sources, *before* proposing.
- A genuinely *wide* audit is not this skill's job — hand it to batch or orchestration tooling.

## Discipline

- Verify before asserting: if a claim is load-bearing and checkable, check it rather than assume — a confident
  guess ("you're guessing") is the cardinal failure.
- Reference the canonical source, not memory or a citing doc.
- Every challenge round must import a genuinely new external bit — reflection with no new information degrades
  the take.
