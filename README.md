# Agent operating policy

An operating policy for coding agents, plus the skills and Claude Code hooks that implement it. Extracted from a one-person company's production setup, minus the company-specific parts.

## What is in here

- `policy/`. Six markdown sources. `universal.md` says when an agent may act without asking: the real-blockers test, the decision ladder, and ticket-derived authority. `coding.md` covers investigation, browser routing, the verification ladder, and git. `orchestration.md` sets one mutation owner per workstream. `review.md` is the code review standard: what a finding must carry, and three severities. Two short files route per harness.
- `generated/`. `CLAUDE.md` and `AGENTS.md`, rendered from those sources; never hand-edited.
- `skills/`. orchestration, handoff, brainstorm, clean-my-ai-harness, unslop, parallel-web-verification, wizard.
- `hooks/`. A PreToolUse guard that refuses unmanaged browser launches from Bash, a SessionEnd checklist, and an example settings block.
- `tools/`. Renderer, installer, tests.

## Policy as source

The harness files are build output. `tools/adapters/render_policy.py` concatenates the harness routing file with the four shared sources and stamps the result with a generation hash, the SHA-256 of the source bytes. `check_generation.py` fails when a committed rendering differs from its sources; CI runs it on every push. A downstream repository can vendor a rendering and pin the expected generation, so a stale copy fails its own build instead of drifting.

Skills use the same idea. A skill that must name its harness writes `{{HARNESS_NAME}}`, `{{AGENT_INSTRUCTIONS_FILE}}`, or `{{SKILLS_DIR}}`. `render_skills.py` substitutes per harness and rejects any other brace-wrapped uppercase name, so a typo cannot ship. `install_skills.py` copies the committed `skills/` tree from HEAD into a runtime directory, and refuses to overwrite a directory it did not create.

## Install

For Claude Code, copy `generated/CLAUDE.md` to `~/.claude/CLAUDE.md`, copy `hooks/*.sh` to `~/.claude/hooks/`, and merge `hooks/settings.example.json` into `~/.claude/settings.json`. Then run `python3 tools/adapters/install_skills.py --harness claude --output-dir ~/.claude/skills`. If that directory already holds skills the installer stops; move them aside or pick another path.

For Codex, copy `generated/AGENTS.md` to `~/.codex/AGENTS.md` and run the installer with `--harness codex --output-dir ~/.agents/skills`.

## What was left out

Anything that only makes sense inside one company: skills bound to its CRM, ticket tracker, reporting pipelines; vendored third-party skills, which have their own upstreams; and the names, identifiers, and paths of the people and systems involved. "The operator" throughout means the one person whose judgment the policy defers to.

The wizard skill is Matt Pocock's, MIT, included with its license file.

Copyright 2026 Bradley Berkman. MIT.
