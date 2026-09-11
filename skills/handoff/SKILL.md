---
name: handoff
description: Compact the current conversation into a handoff document a fresh agent can pick up. Invoke via /handoff.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
---

# Handoff

Write a handoff document summarising the current conversation so a fresh agent can continue the work.

## Where to save

Save to `~/handoffs/handoff-<YYYY-MM-DD-HHMM>.md` (run `date` for the stamp; create the dir if it
doesn't exist). This is a durable, cross-session location — the session scratchpad is per-session, so a new
agent won't find a doc left there. Never save into a project workspace.

## What to include

- **Goal / current focus** — what the work is and where it stands in one or two lines.
- **State** — what's done, what's in flight, what's blocked and on what.
- **Next steps** — the concrete next actions, in order.
- **Suggested skills** — skills the next agent should invoke for this work, by exact invocation path
  (e.g. `/orchestration`, `/brainstorm`, `/unslop`).
- **Key references** — paths, URLs, ticket IDs, branch names, PR links.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor
the doc to that.

## Rules

- Do not duplicate content already captured in other artifacts (specs, plans, ADRs, issues, commits, diffs) —
  reference them by path or URL instead.
- Redact sensitive information: API keys, passwords, tokens, PII.
- Keep it tight — a handoff is a launchpad, not a transcript.

## Deliver

After writing, put the file path on the clipboard (`pbcopy`) and confirm in one line, e.g.:

    Handoff → ~/handoffs/handoff-2026-07-14-1530.md (path copied)
