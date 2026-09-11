# Clean My AI Harness

This skill finds the hidden setup shaping your AI, shows what is helping or getting in the way, and proposes a safer, simpler version.

## Run it

1. Follow `INSTALL.md` for Claude or Codex.
2. Open the project you want to review.
3. Say:

> Use Clean My AI Harness to review the AI setup for this project. Start read-only. Show me one plain-English report of what is helping, what is getting in the way, and what you recommend. Do not change anything until I approve each change.

## Read one report

Open **Your AI Setup** (`YOUR-AI-SETUP.html`). It shows:

- what shapes your AI before you type;
- what protects the work;
- what creates confusion or extra work;
- what the cleaner recommends;
- what it could not see.

The cleaner creates a few supporting files so it can check its work. You do not need to manage them.

The first run changes nothing. To continue, approve or reject each recommendation in chat. The cleaner must ask before touching your setup and leave you a before-and-after when it finishes.

The shared skill supports Claude and Codex while keeping their surface evidence separate. It inspects only the parts the selected product and bounded scope can actually see and control.
