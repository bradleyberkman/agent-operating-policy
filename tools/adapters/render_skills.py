#!/usr/bin/env python3
"""Render harness-token skill sources into harness-facing skill files.

A skill is shared source. When one has to name the harness it runs on, its
instruction file, or where its skills live, it writes a token rather than one
harness's spelling — otherwise the same file is correct in one runtime and wrong
in the other, which is exactly the drift this repository exists to end.

Only files that actually carry a token are rendered. Installing is therefore
"copy the canonical tree, then overlay this harness's rendered files", and the
generated tree stays small enough to read in a review.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"


def git_layout(root: Path = ROOT) -> tuple[Path, str]:
    """Return the containing repository and this checkout's Git prefix.

    The policy project may be checked out as its own repository or consolidated
    under a subdirectory of a larger repository. Git reports paths relative to the
    repository root in both cases, so callers must retain the prefix explicitly.
    """
    repo = Path(
        subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            text=True, capture_output=True, check=True,
        ).stdout.strip()
    ).resolve()
    relative = root.resolve().relative_to(repo)
    prefix = "" if relative == Path(".") else relative.as_posix().rstrip("/") + "/"
    return repo, prefix

# The COMPLETE harness-specific vocabulary. Adding a token here is a deliberate
# widening of what a skill may vary by harness; a skill may use nothing else.
HARNESS_TOKENS: dict[str, dict[str, str]] = {
    "claude": {
        "HARNESS_NAME": "Claude Code",
        "AGENT_INSTRUCTIONS_FILE": "CLAUDE.md",
        "SKILLS_DIR": "~/.claude/skills",
    },
    "codex": {
        "HARNESS_NAME": "Codex",
        "AGENT_INSTRUCTIONS_FILE": "AGENTS.md",
        "SKILLS_DIR": "~/.agents/skills",
    },
}

# Anchored on both sides so the strict form cannot match INSIDE a malformed one.
# Unanchored, `{{{HARNESS_NAME}}}` matched its own inner two braces and rendered as
# `{Claude Code}` — validation passed and stray braces shipped.
TOKEN_RE = re.compile(r"(?<!\{)\{\{([A-Z0-9_]+)\}\}(?!\})")

# Any brace-wrapped occurrence of a name, however many braces and whatever inner
# spacing. Selecting render targets on the strict form alone missed a source carrying
# ONLY `{{ HARNESS_NAME }}`: it was never passed to render_text, so nothing validated it
# and canonical shipped literal braces. Selecting on any `{{` instead is not an option —
# Hugo, Zaraz and Drafts template tags put double braces in a dozen legitimate skills.
# The discriminator is the NAME: a brace-wrapped harness token must be written exactly
# `{{TOKEN}}`; anything else is somebody else's templating and is left alone.
# `\s`, not `[ \t]`: GraphQL-style whitespace includes newlines, and a token split
# across lines as `{{\nHARNESS_NAME\n}}` escaped every check and shipped literally.
# The NAME class is wider than the strict one on purpose. A typo that corrupts a
# separator — `{{HARNESS-NAME}}`, `{{HARNESS NAME}}`, `{{HARNESS/NAME}}` — otherwise
# fails to match at all, so the candidate never enters validation and the literal
# braces ship. Enumerating the allowed separators was the bug: `_.:+-` covered the
# punctuation someone had already typed, not the punctuation someone might. So the
# separator is now ANY run of non-alphanumerics, and the discriminator is carried
# entirely by the letters — the name starts uppercase, every segment is uppercase,
# and no lowercase appears anywhere. That is what keeps other templating out of
# scope: Hugo `{{ .Site.Title }}`, Drafts `{{date}}`, `{{ partial "x" . }}`, Zaraz
# `{{Page URL}}` and `${{ secrets.DEPLOY_TOKEN }}` all carry a lowercase
# letter where a name segment would have to begin.
# `{` and `}` are excluded from the separator so a name can never span a real
# placeholder boundary, and `\n` so an internal newline is not read as a separator.
# Segments end on a name character so trailing junk lands in `trail` rather than in
# the name; otherwise `{HARNESS_NAME }` would carry a trailing space, miss the
# vocabulary check and escape the single-brace rule.
# LEAD and TRAIL therefore have to absorb everything that is not a name character or a
# brace — punctuation included, not just whitespace. With `\s*` there, `{{HARNESS_NAME.}}`
# matched nothing at all: the name cannot end on `.` and the trail could not consume it,
# so a real token with one stray character shipped its braces. They keep `\n` (unlike the
# separator) because that is what catches a token split as `{{\nHARNESS_NAME\n}}`.
# The segment alphabet is the STRICT one, `[A-Z0-9_]`, rather than a narrower guess at
# how a name starts. Requiring an uppercase LETTER first excluded `{{ 2FA_SECRET }}`
# and `{{ _HARNESS_NAME }}` — names TOKEN_RE accepts, so the well-formed spellings
# already fail the build as unknown tokens while the malformed ones shipped braces.
# Anything the strict pattern would claim has to be claimable here too.
_NAME = r"[A-Z0-9_]+(?:[^A-Za-z0-9_{}\n]+[A-Z0-9_]+)*"
_EDGE = r"[^A-Za-z0-9_{}]*"
BRACED_NAME_RE = re.compile(rf"(\{{+)({_EDGE})({_NAME})({_EDGE})(\}}+)")

# The closing run is REQUIRED above, so `{{HARNESS_NAME` — braces never closed at all —
# matched nothing and shipped verbatim. Making the closing optional there is not the
# fix: `{{Page URL}}` would then match with the name `P` and be reported as malformed,
# because `\}}*` succeeds on empty. Two things make this pattern safe instead. The name
# must be MAXIMAL — `(?![A-Za-z0-9_])` stops `P` being carved out of `Page` — and there
# must be no closing brace reachable, so a well-formed placeholder is left entirely to
# BRACED_NAME_RE rather than reported twice.
#
# Scoped to a DOUBLE opening brace on purpose. `{HARNESS_NAME` is the single-brace
# documentation convention with a typo, and flagging it would reintroduce exactly the
# noise the single-brace exemption exists to avoid.
UNCLOSED_NAME_RE = re.compile(rf"\{{\{{{_EDGE}({_NAME})(?![A-Za-z0-9_])(?!{_EDGE}\}})")

# Only this shape can be a well-formed token; anything else brace-wrapped and
# uppercase is a malformed one.
STRICT_NAME_RE = re.compile(r"^[A-Z0-9_]+$")

VOCABULARY = frozenset().union(*(tokens.keys() for tokens in HARNESS_TOKENS.values()))

def candidate_markdown() -> list[Path]:
    """Repository-tracked markdown under `skills/` only.

    A repository-wide rglob reads whatever the working tree holds. A dependency
    document under `node_modules` or `.venv` containing `{{FOO}}` would be selected
    as a skill source and then fail rendering as an unknown token, and an untracked
    file using a real token would produce generated output for content the projection
    deliberately refuses to copy.
    """
    repo, prefix = git_layout(ROOT)
    prefix = prefix + "skills/"
    listed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        text=True, capture_output=True, check=True,
    ).stdout
    relative_names = []
    for name in listed.split("\0"):
        if not name or not name.endswith(".md") or not name.startswith(prefix):
            continue
        relative_names.append(name[len(prefix):])
    return sorted(SKILLS / name for name in relative_names)


def skill_sources() -> list[Path]:
    """Every markdown skill source carrying at least one harness token."""
    found: list[Path] = []
    for path in candidate_markdown():
        if not path.is_file():
            continue
        rel = path.relative_to(SKILLS)
        text = path.read_text()
        # Malformed harness tokens make a file a render target too, so that render_text
        # gets the chance to reject it rather than the file slipping through unvalidated.
        if TOKEN_RE.search(text) or malformed_tokens(text):
            found.append(path)
    return found


def malformed_tokens(text: str) -> list[str]:
    """Brace-wrapped placeholders that would ship literal braces to an agent.

    Two rules, because the safe breadth differs:

    * A name in the vocabulary is rejected at ANY brace count when not written
      exactly `{{TOKEN}}` — `{{{HARNESS_NAME}}}`, `{{ HARNESS_NAME }}` and
      `{HARNESS_NAME}` are all somebody meaning the token and missing.
    * A name NOT in the vocabulary is rejected only at two or more braces. A
      misspelling like `{{ HARNES_NAM }}` escapes both the strict pattern and the
      vocabulary check, so it would otherwise ship verbatim. Single braces are left
      alone: `{CF_API_TOKEN}`, `{ACCOUNT_ID}` and `{SLUG}` are an ordinary
      documentation convention in vendored skill references, and flagging them would be pure noise.
    """
    found: list[str] = []
    for match in BRACED_NAME_RE.finditer(text):
        opening, lead, name, trail, closing = match.groups()
        strict = (
            opening == "{{"
            and closing == "}}"
            and not lead
            and not trail
            and STRICT_NAME_RE.match(name)
        )
        if strict:
            continue
        # EITHER side, not just the opening one: `{ HARNES_NAM }}` is a misspelling that
        # also dropped a brace, and checking only the opening count let it ship. No
        # tracked file uses an asymmetric brace placeholder legitimately.
        if name in VOCABULARY or len(opening) >= 2 or len(closing) >= 2:
            found.append(match.group(0))
    # Never closed at all. Two braces is already the threshold at which an unknown name
    # is rejected, so no extra vocabulary test is needed here.
    found.extend(match.group(0) for match in UNCLOSED_NAME_RE.finditer(text))
    return found


def render_text(text: str, harness: str, where: str) -> str:
    """Substitute every token, failing closed on one this vocabulary lacks."""
    tokens = HARNESS_TOKENS[harness]
    unknown = sorted({m.group(1) for m in TOKEN_RE.finditer(text)} - tokens.keys())
    if unknown:
        raise KeyError(f"{where}: unknown harness token(s): {', '.join(unknown)}")
    # A harness token written loosely would survive the substitution below and ship a
    # literal brace into a runtime skill. Checked by name rather than by looking for any
    # leftover `{{`, so a skill that legitimately documents Hugo or Drafts template tags
    # can still carry a harness token.
    malformed = sorted(set(malformed_tokens(text)))
    if malformed:
        raise ValueError(f"{where}: malformed harness token(s): {', '.join(malformed)}")
    return TOKEN_RE.sub(lambda m: tokens[m.group(1)], text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "generated" / "skills")
    args = parser.parse_args()
    sources = skill_sources()
    try:
        for harness in HARNESS_TOKENS:
            expected: set[Path] = set()
            for source in sources:
                rel = source.relative_to(SKILLS)
                expected.add(rel)
                target = args.output_dir / harness / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(render_text(source.read_text(), harness, str(rel)))
            # A source that loses its last token, or is renamed or deleted, leaves a
            # rendering behind. Writing only the current set left it there, and
            # check_generation then reported it as "no longer tokenised" — a state the
            # documented render-then-check workflow could not repair.
            harness_dir = args.output_dir / harness
            if harness_dir.is_dir():
                for stale in sorted(harness_dir.rglob("*.md")):
                    if stale.relative_to(harness_dir) not in expected:
                        stale.unlink()
                for empty in sorted(harness_dir.rglob("*"), reverse=True):
                    if empty.is_dir() and not any(empty.iterdir()):
                        empty.rmdir()
    except (KeyError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"rendered {len(sources)} tokenised skill source(s) for {len(HARNESS_TOKENS)} harnesses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
