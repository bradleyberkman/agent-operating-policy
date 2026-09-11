#!/usr/bin/env python3
"""Fail when a checked rendering differs from canonical policy."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from render_policy import HARNESSES, ROOT, render
from render_skills import HARNESS_TOKENS, SKILLS, render_text, skill_sources


def check_skills(output_dir: Path) -> list[str]:
    """Skill renderings drift the same way policy does, and are gated the same way.

    A stale rendering is worse here than a missing one: the runtime keeps working
    while silently serving a harness the other harness's naming.
    """
    failures: list[str] = []
    sources = skill_sources()
    for harness in HARNESS_TOKENS:
        expected = {source.relative_to(SKILLS) for source in sources}
        harness_dir = output_dir / harness
        present = {
            path.relative_to(harness_dir)
            for path in harness_dir.rglob("*.md")
        } if harness_dir.is_dir() else set()
        for rel in sorted(expected - present):
            failures.append(f"skills/{harness}/{rel} missing")
        # A source that stops using tokens must stop being rendered, or the overlay
        # keeps installing a file canonical no longer knows about.
        for rel in sorted(present - expected):
            failures.append(f"skills/{harness}/{rel} is rendered but no longer tokenised")
        for rel in sorted(expected & present):
            want = render_text((SKILLS / rel).read_text(), harness, str(rel))
            if (harness_dir / rel).read_text() != want:
                failures.append(f"skills/{harness}/{rel} differs from canonical source")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "generated")
    args = parser.parse_args()
    failures: list[str] = []
    for filename in HARNESSES:
        target = args.output_dir / filename
        if not target.exists():
            failures.append(f"{filename} missing")
        elif target.read_text() != render(filename):
            failures.append(f"{filename} differs from canonical policy")
    try:
        failures.extend(check_skills(args.output_dir / "skills"))
    except (KeyError, ValueError) as error:
        failures.append(str(error))
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("policy and skill renderings match canonical sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
