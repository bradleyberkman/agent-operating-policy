#!/bin/bash
# Session-end closing checklist. Advisory — surfaces
# lingering state, never mutates. Runs on SessionEnd in whatever cwd the
# session held; silent unless something needs attention.
cd "$(pwd)" 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
br=$(git branch --show-current 2>/dev/null); [ -z "$br" ] && exit 0
def=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|.*/||'); def=${def:-main}
[ "$br" = "$def" ] && exit 0
msgs=""
git rev-parse --verify -q "origin/$br" >/dev/null || msgs="$msgs\n- branch '$br' has no remote — unpublished work"
[ -n "$(git status --porcelain 2>/dev/null)" ] && msgs="$msgs\n- uncommitted changes in the worktree"
ahead=$(git rev-list --count "origin/$br..$br" 2>/dev/null) && [ "${ahead:-0}" -gt 0 ] && msgs="$msgs\n- $ahead local commit(s) not pushed"
[ -n "$msgs" ] && printf 'Closing checklist:%b\n(Verify: workspace archived, branch gone after merge, tracker status truthful, docs attached.)\n' "$msgs"
exit 0
