#!/usr/bin/env python3
"""Render shared policy into harness-facing instruction files."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ("universal.md", "coding.md", "review.md", "orchestration.md")
HARNESSES = {"CLAUDE.md": "harness-claude.md", "AGENTS.md": "harness-codex.md"}


def source_bytes() -> bytes:
    names = (*SHARED, *HARNESSES.values())
    return b"\0".join((ROOT / "policy" / name).read_bytes() for name in names)


def render(filename: str) -> str:
    generation = hashlib.sha256(source_bytes()).hexdigest()
    parts = [
        "<!-- Generated from policy/*.md; do not edit this rendering directly. -->",
        f"<!-- Policy generation: `{generation}` -->",
        (ROOT / "policy" / HARNESSES[filename]).read_text().strip(),
    ]
    parts.extend((ROOT / "policy" / name).read_text().strip() for name in SHARED)
    return "\n\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "generated")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename in HARNESSES:
        (args.output_dir / filename).write_text(render(filename))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
