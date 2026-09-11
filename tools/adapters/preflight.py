#!/usr/bin/env python3
"""Read-only policy/skill distribution preflight for local harnesses."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def git(checkout: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=checkout, text=True, capture_output=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def remote_main(checkout: Path) -> str:
    result = subprocess.run(
        ["git", "ls-remote", "--exit-code", "origin", "refs/heads/main"],
        cwd=checkout, text=True, capture_output=True, check=False
    )
    if result.returncode != 0 or not result.stdout.strip():
        return "unavailable"
    return result.stdout.split()[0]


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def generation(path: Path) -> str | None:
    if not path.is_file():
        return None
    match = re.search(r"Policy generation: `([0-9a-f]{64})`", path.read_text())
    return match.group(1) if match else None


def inspect(
    checkout: Path, claude_policy: Path, codex_policy: Path,
    repository_marker: Path | None = None,
    refresh: bool = False,
) -> dict:
    expected_repository_generation = None
    if repository_marker:
        expected_repository_generation = json.loads(repository_marker.read_text()).get(
            "expected_generation"
        )
    return {
        "canonical_checkout": str(checkout),
        "remote_main": remote_main(checkout) if refresh else None,
        "checkout_status": git(checkout, "status", "--short"),
        "checkout_head": git(checkout, "rev-parse", "HEAD"),
        "checkout_origin_main": git(checkout, "rev-parse", "origin/main"),
        "canonical_generation": generation(checkout / "generated" / "AGENTS.md"),
        "repository_expected_generation": expected_repository_generation,
        "policy": {
            "claude": {
                "installed": digest(claude_policy),
                "expected": digest(checkout / "generated" / "CLAUDE.md"),
            },
            "codex": {
                "installed": digest(codex_policy),
                "expected": digest(checkout / "generated" / "AGENTS.md"),
            },
        },
    }


def failures(report: dict) -> list[str]:
    problems = []
    if report["checkout_status"]:
        problems.append("canonical checkout is dirty")
    if report["remote_main"] == "unavailable":
        problems.append("could not read remote main")
    if report["checkout_head"] == "unavailable" or report["checkout_origin_main"] == "unavailable":
        problems.append("canonical checkout or origin/main is unavailable")
    else:
        authoritative_main = report["remote_main"] or report["checkout_origin_main"]
        if report["checkout_head"] != authoritative_main:
            problems.append("canonical checkout is not exactly at remote main")
    for harness, policy in report["policy"].items():
        if policy["installed"] != policy["expected"]:
            problems.append(f"{harness} policy differs from canonical rendering")
    if (
        report["repository_expected_generation"] is not None
        and report["repository_expected_generation"] != report["canonical_generation"]
    ):
        problems.append("repository expects a different global policy generation")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, default=ROOT)
    parser.add_argument("--claude-policy", type=Path, default=Path.home() / ".claude/CLAUDE.md")
    parser.add_argument("--codex-policy", type=Path, default=Path.home() / ".codex/AGENTS.md")
    parser.add_argument("--repository-marker", type=Path)
    args = parser.parse_args()
    report = inspect(
        args.checkout, args.claude_policy, args.codex_policy, args.repository_marker,
        refresh=True,
    )
    report["failures"] = failures(report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
