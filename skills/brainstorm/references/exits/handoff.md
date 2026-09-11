# Exit: Handoff prompt (fresh session)

When the thinking is done but execution belongs in a fresh session (context is heavy, or the work wants an
unbiased start), produce a **clipboard-ready handoff prompt** rather than executing here.

## Rules

- Put the complete prompt on the clipboard the same turn (`pbcopy` or the platform equivalent), and confirm in one line.
- Include: the circumstance, what was decided *together*, the open questions, and links — enough for a fresh
  agent to pick up cleanly.
- Same discipline as capture: record what was genuinely co-derived; don't smuggle in a unilateral prescribed
  plan or "recommended first steps" the user didn't agree to.
- This is the natural terminal for a brainstorm that lands on "yes, build it — but not in this context."
