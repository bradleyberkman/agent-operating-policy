#!/usr/bin/env python3
"""Materialise a harness's skill projection.

Rendering alone changes nothing a harness can see. `~/.agents/skills` and
`~/.claude/skills` are read DIRECTLY by their runtimes, so a canonical skill
carrying `{{HARNESS_NAME}}` is served to the agent verbatim unless something
projects the rendered form over it. This is that step: canonical tree first,
then this harness's rendered files on top.

DORMANT BY DEFAULT. It writes only where `--output-dir` points and never
discovers a runtime directory on its own. Repointing a live harness at a
projection is a separate, deliberate act, because it replaces
directories that currently hold unreviewed local work.
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from render_skills import (
    BRACED_NAME_RE,
    HARNESS_TOKENS,
    ROOT,
    SKILLS,
    TOKEN_RE,
    malformed_tokens,
    render_text,
    git_layout,
)

# Only the `skills/` subtree is projected: policy, tools, hooks and repository
# documentation are machinery, not skills a runtime should load.
SKILLS_SUBTREE = "skills"


# Written into every projection so a rerun can tell a directory it created from one it
# must not touch. Without it the only safe rule would be "never reuse a path".
MARKER = ".skill-projection"
# Prefix for the transient backup of a projection being replaced. Uniquely suffixed
# per install, so a collision can never make this tool delete something it did not
# create; grep for it beside a destination to recover from a hard interruption.
PREVIOUS_PREFIX = ".skill-projection-previous-"


def extract_head(into: Path) -> int:
    """Materialise the committed tree at HEAD, not the working tree.

    Listing tracked paths and then copying them proves only that each PATH is
    tracked — the CONTENT still came from the working tree, so running the installer
    from a dirty checkout published unstaged edits, and any secret pasted into a
    tracked file, straight into the runtime. `git archive` reads the commit, so a
    dirty checkout cannot leak through, and it preserves file modes.
    """
    repo, prefix = git_layout(ROOT)
    treeish = f"HEAD:{prefix}{SKILLS_SUBTREE}"
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", treeish],
        capture_output=True, check=True,
    ).stdout
    extracted = 0
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        for member in bundle.getmembers():
            if not member.isfile():
                continue
            bundle.extract(member, into, filter="data")
            extracted += 1
    return extracted


# Archiving the sources from HEAD does not make the projection reviewed: the rendering
# LOGIC still comes from the working tree. A local edit to HARNESS_TOKENS changes what
# gets published without changing any archived file, so the adapters are pinned too.
RENDERING_ADAPTERS = ("tools/adapters/render_skills.py", "tools/adapters/install_skills.py")


def assert_adapters_match_head() -> None:
    """Refuse to project when the rendering logic differs from the commit."""
    repo, prefix = git_layout(ROOT)
    dirty = []
    for rel in RENDERING_ADAPTERS:
        committed = subprocess.run(
            ["git", "-C", str(repo), "show", f"HEAD:{prefix}{rel}"],
            capture_output=True, check=True,
        ).stdout
        if committed != (ROOT / rel).read_bytes():
            dirty.append(rel)
    if dirty:
        raise ValueError(
            "refusing to project with uncommitted rendering logic: "
            + ", ".join(dirty)
            + " — the archived sources would be rendered by unreviewed code"
        )


def marker_harness(marker: Path) -> str | None:
    """The harness a projection was built for, from its own marker file."""
    for line in marker.read_text().splitlines():
        if line.startswith("harness="):
            return line[len("harness="):].strip()
    return None


def guard_output_dir(output_dir: Path, harness: str) -> Path:
    """Refuse any target that would destroy the checkout or unreviewed work.

    Returns the path every later operation must use, because validating one path and
    then writing to another was the defect. `--output-dir` pointing at a SYMLINK
    inside the checkout resolved to somewhere harmless and passed, but
    `mkdtemp(dir=output_dir.parent)` and `replace()` then acted on the UNRESOLVED
    path — so the staging tree and the swap landed inside the canonical checkout the
    guard had just approved staying out of.

    Both forms are therefore checked: the resolved one, and the purely lexical one
    that follows no symlink at all. A path is refused if EITHER lands in the
    checkout, so neither direction of symlink can launder it.
    """
    out = output_dir.resolve()
    lexical = Path(os.path.abspath(output_dir))
    root = ROOT.resolve()
    for candidate in (out, lexical):
        if candidate == root or root.is_relative_to(candidate):
            raise ValueError(f"{candidate} contains the canonical checkout; refusing to erase it")
        if candidate.is_relative_to(root):
            raise ValueError(
                f"{candidate} is inside the canonical checkout; projections go elsewhere"
            )
    if out.exists():
        if not out.is_dir():
            raise ValueError(f"{out} exists and is not a directory")
        # A directory this tool did not create may be a live runtime holding local work
        # — ~/.agents/skills and ~/.claude/skills are exactly that, and the README names
        # them, so they are the first paths anyone will try.
        if any(out.iterdir()) and not (out / MARKER).is_file():
            raise ValueError(
                f"{out} is not empty and carries no {MARKER}; refusing to replace "
                "a directory this tool did not create"
            )
        # Owning the directory is not enough — it must be OUR harness's. The marker has
        # recorded `harness=` since the first version and nothing read it, so pointing a
        # Codex install at a Claude projection replaced a live runtime with the other
        # harness's text and reported success. Reusing a path across harnesses has to be
        # a deliberate removal, not a silent overwrite.
        if (out / MARKER).is_file():
            existing = marker_harness(out / MARKER)
            if existing and existing != harness:
                raise ValueError(
                    f"{out} is a {existing} projection; refusing to overwrite it with "
                    f"{harness}. Remove it deliberately, or project {harness} elsewhere"
                )
    return out


def leaked_tokens(tree: Path, harness: str) -> str | None:
    """First surviving placeholder in a built tree, if any.

    Shares BRACED_NAME_RE rather than keeping a second, narrower pattern. The private
    copy accepted only whitespace around the name, so every spelling the renderer
    learned to reject — punctuated separators, a stray trailing character — this
    backstop silently passed. A guard that lags the thing it guards is worse than none,
    because it reports clean.
    """
    for path in sorted(tree.rglob("*.md")):
        for match in BRACED_NAME_RE.finditer(path.read_text()):
            if match.group(3) in HARNESS_TOKENS[harness]:
                return f"{path.relative_to(tree)}: projection still carries {match.group(0)}"
    return None


def tree_entries(tree: Path) -> set[Path]:
    """Every relative path in a tree, including broken and directory symlinks."""
    entries: set[Path] = set()
    for current, directories, files in os.walk(tree, followlinks=False):
        parent = Path(current)
        for name in directories + files:
            rel = (parent / name).relative_to(tree)
            if rel != Path(MARKER):
                entries.add(rel)
    return entries


def refuse_retained_content_loss(existing: Path, replacement: Path) -> None:
    """Stop before a refresh would discard content outside the new projection.

    The marker proves this installer created the canonical base. It does not claim
    ownership of provider packages or local additions made afterward. A refresh may
    update shared paths, but removing a path requires an explicit reconciliation and
    isolated cutover where the retained content can be verified.
    """
    if not existing.exists():
        return
    extras = tree_entries(existing) - tree_entries(replacement)
    if not extras:
        return

    # Report the smallest useful set. If an entire retained directory is absent from
    # the replacement, naming every descendant obscures the actual preservation unit.
    roots: list[Path] = []
    for rel in sorted(extras, key=lambda item: (len(item.parts), str(item))):
        if not any(parent == rel or parent in rel.parents for parent in roots):
            roots.append(rel)
    shown = ", ".join(str(path) for path in roots[:8])
    suffix = "" if len(roots) <= 8 else f", and {len(roots) - 8} more"
    raise ValueError(
        f"refresh would delete retained content: {shown}{suffix}. "
        "Build an isolated replacement that preserves or explicitly resolves it"
    )


def project(
    harness: str, output_dir: Path, *, allow_uncommitted_adapters: bool = False
) -> tuple[int, int]:
    """Build a complete projection, then replace the destination in one step.

    The destination may already be a live runtime. Deleting it first meant a
    malformed source, a git failure, a filesystem error or a surviving token left
    that runtime missing or half-populated, with no way back to the previous good
    projection. Everything is built and validated in a sibling directory, and the
    destination is only touched once the replacement is known good.
    """
    if not allow_uncommitted_adapters:
        assert_adapters_match_head()
    # Rebound, not just validated: every path operation below must be the one the guard
    # approved, or a symlink makes the two diverge.
    output_dir = guard_output_dir(output_dir, harness)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=output_dir.parent, prefix=".skill-projection-"))
    try:
        copied, rendered = build(harness, staging)
        leak = leaked_tokens(staging, harness)
        if leak:
            raise ValueError(leak)
        refuse_retained_content_loss(output_dir, staging)
        swap(staging, output_dir)
        return copied, rendered
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def swap(staging: Path, output_dir: Path) -> None:
    """Move the new projection into place without a window where nothing exists.

    Deleting the destination and then renaming is two operations: an interruption
    between them leaves the runtime entirely absent. Instead the previous projection
    is renamed ASIDE — itself atomic — and only removed once the replacement is
    installed, so every intermediate state has a complete tree somewhere. If the
    second rename fails the old one is put straight back, and if the process is
    killed between the two the previous projection is intact beside the destination
    under the PREVIOUS_PREFIX name rather than gone.

    The backup path is allocated UNIQUELY. A fixed name would collide with whatever
    already sits beside the destination, and this function deletes what it finds
    there — bypassing the ownership guard the destination itself gets, and erasing
    unrelated local work.
    """
    backup: Path | None = None
    if output_dir.exists():
        # mkdtemp both allocates a free name and creates it. Renaming a directory onto
        # an existing EMPTY directory is permitted, so the move stays a single atomic
        # operation rather than a delete followed by a rename.
        backup = Path(tempfile.mkdtemp(dir=output_dir.parent, prefix=PREVIOUS_PREFIX))
        output_dir.replace(backup)
    try:
        staging.replace(output_dir)
    except BaseException:
        # Includes KeyboardInterrupt: a cancelled install must not eat the runtime.
        if backup is not None and not output_dir.exists():
            backup.replace(output_dir)
        raise
    if backup is not None:
        shutil.rmtree(backup, ignore_errors=True)


def build(harness: str, output_dir: Path) -> tuple[int, int]:
    """Materialise HEAD, then render this harness's tokens in place."""
    (output_dir / MARKER).write_text(f"harness={harness}\n")
    copied = extract_head(output_dir)

    # Render over the EXTRACTED tree rather than re-reading the working tree, so the
    # rendered content comes from the same commit as everything around it. Anything
    # extract_head skipped is simply not present, so nothing can be conjured back in.
    rendered = 0
    for path in sorted(output_dir.rglob("*.md")):
        rel = path.relative_to(output_dir)
        text = path.read_text()
        if not (TOKEN_RE.search(text) or malformed_tokens(text)):
            continue
        path.write_text(render_text(text, harness, str(rel)))
        rendered += 1
    return copied, rendered


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness", required=True, choices=sorted(HARNESS_TOKENS))
    parser.add_argument("--output-dir", type=Path, required=True)
    # Deliberately a typed flag rather than an environment variable: an ambient opt-out
    # would silently disable the guard for every caller that inherited it. This one has
    # to be written on the command line, and it says so in the output.
    parser.add_argument(
        "--allow-uncommitted-adapters",
        action="store_true",
        help="project with unreviewed rendering logic (development only)",
    )
    args = parser.parse_args()
    if args.allow_uncommitted_adapters:
        print("WARNING: projecting with UNREVIEWED rendering logic", file=sys.stderr)
    try:
        copied, rendered = project(
            args.harness,
            args.output_dir,
            allow_uncommitted_adapters=args.allow_uncommitted_adapters,
        )
    except (KeyError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"projected {copied} file(s) for {args.harness}, {rendered} rendered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
