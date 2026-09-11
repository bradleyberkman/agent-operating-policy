# Install the Claude edition

This installs the skill into **claude.ai**, which takes an uploaded archive. That is a different
path from Claude Code, which loads this directory from disk and needs no install step at all.

The archive is a build artifact and is deliberately not committed — it would be a second copy of
every file in this directory, drifting from it the moment either changed. Build it from the
checkout instead:

```sh
cd ~/.claude/skills
rm -f clean-my-ai-harness-claude.zip
zip -qr clean-my-ai-harness-claude.zip clean-my-ai-harness \
  -x '*/__pycache__/*' '*.pyc' '*/.DS_Store'
```

That produces a single top-level `clean-my-ai-harness/` folder with `SKILL.md` at its root, which
is the shape the upload expects. Rebuild it after any change to this directory; the upload carries
no link back to the repository.

1. In Claude, enable **Code execution and file creation** under **Settings > Capabilities**.
2. Open **Customize > Skills**.
3. Click **+**, choose **Create skill**, then **Upload a skill**.
4. Upload the `clean-my-ai-harness-claude.zip` you just built, and enable it.
5. Start a new chat with the project you want to review and say:

> Use clean-my-ai-harness to review the AI setup for this project. Start read-only. Show me one plain-English report. Do not change anything until I approve each change.

The report will say what Claude could not see. If your instructions live outside the project, add or export them before running the review.

To remove the cleaner, disable or delete it under **Customize > Skills**. That does not undo changes you previously approved; use the rollback instructions from that run.
