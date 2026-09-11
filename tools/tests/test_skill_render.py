import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ROOT
ADAPTERS = ROOT / "tools" / "adapters"
RENDER = ADAPTERS / "render_skills.py"
CHECK = ADAPTERS / "check_generation.py"
RENDER_POLICY = ADAPTERS / "render_policy.py"

sys.path.insert(0, str(ADAPTERS))
from render_skills import HARNESS_TOKENS, render_text, skill_sources

# Every end-to-end rendering test builds this file in a throwaway CLONE of the
# repository rather than pointing at a real skill.
#
# Twice now a test asserted on whichever corpus file happened to carry a token, and
# twice the token turned out not to belong there: one was on a harness capability, and
# one made a Codex projection of a skill that loads a Claude-only directory and
# declares Claude-only tools. Both times the
# suite stayed green while the thing it was demonstrating was wrong. A fixture cannot
# do that — it tests the RENDERER, and whether any shipped skill should carry a token
# is a separate question, answered separately by the corpus-wide malformed scan.
TOKENISED = Path("token-fixture") / "SKILL.md"  # relative to skills/ and to a projection
MARKER_NAME = ".skill-projection"
TOKENISED_BODY = (
    "Runs on {{HARNESS_NAME}}; instructions live in {{AGENT_INSTRUCTIONS_FILE}} "
    "and skills in {{SKILLS_DIR}}.\n"
)


class SkillRenderTests(unittest.TestCase):
    def run_tool(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", *map(str, args)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def render_all(self, out: Path) -> None:
        """Both renderers, so the drift gate sees a complete generated tree."""
        self.assertEqual(self.run_tool(RENDER_POLICY, "--output-dir", out).returncode, 0)
        result = self.run_tool(RENDER, "--output-dir", out / "skills")
        self.assertEqual(result.returncode, 0, result.stderr)

    def git_fixture(self, tmp: str, rel: str, body: str) -> Path:
        """A real repository, because source discovery honours git tracking now."""
        root = Path(tmp)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        target = root / "skills" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        return root

    def test_each_harness_gets_its_own_naming(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clone, out = self.tokenised_clone(Path(tmp)), Path(tmp) / "generated"
            self.render_all_in(clone, out)
            claude = (out / "skills" / "claude" / TOKENISED).read_text()
            codex = (out / "skills" / "codex" / TOKENISED).read_text()
            self.assertIn("Runs on Claude Code; instructions live in CLAUDE.md", claude)
            self.assertIn("skills in ~/.claude/skills", claude)
            self.assertIn("Runs on Codex; instructions live in AGENTS.md", codex)
            self.assertIn("skills in ~/.agents/skills", codex)
            # Neither rendering may leak the other harness's naming.
            for wrong in ("Codex", "AGENTS.md", "~/.agents/skills"):
                self.assertNotIn(wrong, claude, wrong)
            for wrong in ("Claude Code", "CLAUDE.md", "~/.claude/skills"):
                self.assertNotIn(wrong, codex, wrong)
            # A harness-specific CAPABILITY is never tokenised. A skill whose install
            # flow or tool dispatch exists on one harness only stays prose, because
            # rendering a harness NAME into it would promise a flow that does not exist.

    def test_no_rendering_ships_an_unsubstituted_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.render_all(out)
            for path in (out / "skills").rglob("*.md"):
                self.assertNotIn("{{", path.read_text(), f"{path} shipped a raw token")

    def test_an_unknown_token_fails_closed(self) -> None:
        # A skill inventing its own token must not render to a literal brace or to
        # an empty string — either would ship broken prose into a runtime.
        for harness in HARNESS_TOKENS:
            with self.assertRaises(KeyError):
                render_text("see {{NO_SUCH_TOKEN}} here", harness, "fixture.md")

    def test_a_malformed_token_fails_closed(self) -> None:
        for harness in HARNESS_TOKENS:
            with self.assertRaises(ValueError):
                render_text("see {{ HARNESS_NAME }} here", harness, "fixture.md")

    def test_a_malformed_only_source_is_still_a_render_target(self) -> None:
        # Selecting on the strict form alone let a source carrying ONLY a loose token
        # skip validation entirely, so canonical kept literal braces and the install
        # copied them. It must be selected precisely so render_text can reject it.
        import render_skills

        with tempfile.TemporaryDirectory() as tmp:
            root = self.git_fixture(tmp, "loose-skill/SKILL.md", "runs on {{ HARNESS_NAME }}\n")
            with unittest.mock.patch.object(render_skills, "ROOT", root), \
                    unittest.mock.patch.object(render_skills, "SKILLS", root / "skills"):
                sources = render_skills.skill_sources()
            self.assertEqual([p.name for p in sources], ["SKILL.md"])

    def test_other_template_syntax_is_left_alone(self) -> None:
        # A dozen skills legitimately document Hugo, Zaraz and Drafts template tags.
        # Treating every '{{' as a harness token would make all of them render targets.
        import render_skills

        with tempfile.TemporaryDirectory() as tmp:
            root = self.git_fixture(
                tmp, "hugo-skill/SKILL.md",
                "{{ .Site.Title }} and {{date}} and {{ partial \"x\" . }} and {CF_API_TOKEN}\n",
            )
            with unittest.mock.patch.object(render_skills, "ROOT", root), \
                    unittest.mock.patch.object(render_skills, "SKILLS", root / "skills"):
                self.assertEqual(render_skills.skill_sources(), [])
        for harness in HARNESS_TOKENS:
            # …and such a file renders untouched if it also carries a real token.
            out = render_text("{{ .Site.Title }} on {{HARNESS_NAME}}", harness, "f.md")
            self.assertIn("{{ .Site.Title }}", out)
            self.assertNotIn("{{HARNESS_NAME}}", out)

    def test_shipped_skills_carry_no_malformed_harness_token(self) -> None:
        # Scoped to what the renderer considers a skill: tracked markdown under
        # skills/. Repository docs are never installed into a runtime.
        # The Git-tracked list, not an rglob. A repository-wide walk reads whatever the
        # working tree holds, so an ignored `.venv/**/README.md` containing `{{ FOO }}`
        # failed this test over a file the projection refuses to copy — the suite
        # depended on how clean the checkout happened to be. This is the same candidate
        # set the renderer selects from, which is the set that can actually ship.
        import render_skills

        for path in render_skills.candidate_markdown():
            self.assertEqual(
                render_skills.malformed_tokens(path.read_text()), [],
                f"{path} carries a loosely written harness token",
            )

    def test_extra_braces_are_rejected_not_partially_substituted(self) -> None:
        # Unanchored, the strict pattern matched the INNER two braces of
        # `{{{HARNESS_NAME}}}` and rendered `{Claude Code}` — validation passed and
        # stray braces shipped.
        for harness in HARNESS_TOKENS:
            with self.assertRaises(ValueError):
                render_text("see {{{HARNESS_NAME}}} here", harness, "fixture.md")
            with self.assertRaises(ValueError):
                render_text("see {HARNESS_NAME} here", harness, "fixture.md")

    def test_a_misspelled_malformed_token_is_rejected(self) -> None:
        # Both misspelled AND malformed slipped every gate: not strict, so the token
        # pattern missed it; not in the vocabulary, so the malformed check skipped it.
        for harness in HARNESS_TOKENS:
            with self.assertRaises(ValueError):
                render_text("see {{ HARNES_NAM }} here", harness, "fixture.md")

    def test_asymmetric_braces_are_rejected_on_either_side(self) -> None:
        # A misspelling that also drops a brace. Counting only the opening side let
        # `{ HARNES_NAM }}` through discovery, rendering and the leak guard alike.
        import render_skills

        for text in ("{ HARNES_NAM }}", "{{ HARNES_NAM }", "{HARNES_NAM}}"):
            self.assertNotEqual(
                render_skills.malformed_tokens(text), [], f"{text} was accepted"
            )
        for harness in HARNESS_TOKENS:
            with self.assertRaises(ValueError):
                render_text("see { HARNES_NAM }} here", harness, "fixture.md")

    def test_single_brace_documentation_placeholders_are_left_alone(self) -> None:
        # `{CF_API_TOKEN}`, `{ACCOUNT_ID}` and `{SLUG}` are an ordinary documentation
        # convention used dozens of times across vendored skill references. Rejecting
        # every uppercase placeholder would be pure noise.
        import render_skills

        self.assertEqual(
            render_skills.malformed_tokens("run with {CF_API_TOKEN} and {ACCOUNT_ID}"), []
        )

    def test_regeneration_prunes_an_orphaned_rendering(self) -> None:
        # A source that loses its last token, or is renamed, left its rendering behind.
        # check_generation then reported "no longer tokenised" — a state the documented
        # render-then-check workflow could not repair.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.render_all(out)
            orphan = out / "skills" / "codex" / "retired-skill" / "SKILL.md"
            orphan.parent.mkdir(parents=True, exist_ok=True)
            orphan.write_text("left behind\n")
            self.assertEqual(self.run_tool(CHECK, "--output-dir", out).returncode, 1)
            # Re-running the renderer alone must restore a passing tree.
            self.assertEqual(
                self.run_tool(RENDER, "--output-dir", out / "skills").returncode, 0
            )
            self.assertFalse(orphan.exists())
            self.assertEqual(self.run_tool(CHECK, "--output-dir", out).returncode, 0)

    def test_a_failed_projection_leaves_the_previous_one_intact(self) -> None:
        # The destination may be a live runtime. Deleting it before building meant any
        # failure left that runtime missing or half-populated.
        import install_skills

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "projection"
            self.assertEqual(
                self.run_tool(
                    ADAPTERS / "install_skills.py",
                    "--harness", "claude", "--output-dir", dest, "--allow-uncommitted-adapters",
                ).returncode,
                0,
            )
            before = sorted(p.name for p in dest.rglob("*"))
            self.assertIn("handoff", before)
            with unittest.mock.patch.object(
                install_skills, "build", side_effect=OSError("disk full")
            ), self.assertRaises(OSError):
                install_skills.project("claude", dest, allow_uncommitted_adapters=True)
            self.assertEqual(sorted(p.name for p in dest.rglob("*")), before)
            self.assertFalse(any(dest.parent.glob(".skill-projection-*")))

    def test_a_failed_swap_restores_the_previous_projection(self) -> None:
        # rmtree-then-rename left a window with nothing at the destination. The rename
        # aside is atomic, so a failure during the second rename must put it back.
        import install_skills

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "projection"
            self.assertEqual(
                self.run_tool(
                    ADAPTERS / "install_skills.py",
                    "--harness", "codex", "--output-dir", dest, "--allow-uncommitted-adapters",
                ).returncode,
                0,
            )
            before = sorted(p.name for p in dest.rglob("*"))
            original_replace = Path.replace
            calls = {"n": 0}

            def flaky(self_path, target):
                calls["n"] += 1
                if calls["n"] == 2:  # the staging -> destination rename
                    raise OSError("interrupted mid-swap")
                return original_replace(self_path, target)

            with unittest.mock.patch.object(Path, "replace", flaky), \
                    self.assertRaises(OSError):
                install_skills.project("codex", dest, allow_uncommitted_adapters=True)
            self.assertTrue(dest.is_dir(), "the previous projection was not restored")
            self.assertEqual(sorted(p.name for p in dest.rglob("*")), before)
            self.assertFalse(any(dest.parent.glob(".skill-projection-previous-*")))

    def test_swap_never_deletes_an_unowned_backup_collision(self) -> None:
        # A fixed backup name would collide with whatever sits beside the destination,
        # and the swap deletes what it finds there — bypassing the ownership guard the
        # destination itself gets.
        import install_skills

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "projection"
            squatter = Path(tmp) / f"{install_skills.PREVIOUS_PREFIX}projection"
            squatter.mkdir()
            (squatter / "unrelated-local-work.md").write_text("do not delete me\n")
            for _ in range(2):
                self.assertEqual(
                    self.run_tool(
                        ADAPTERS / "install_skills.py",
                        "--harness", "claude", "--output-dir", dest,
                        "--allow-uncommitted-adapters",
                    ).returncode,
                    0,
                )
            self.assertTrue(
                (squatter / "unrelated-local-work.md").is_file(),
                "an unowned directory at the backup path was destroyed",
            )

    def test_projection_renders_the_whole_tree_for_a_harness(self) -> None:
        # Rendering alone changes nothing a harness can see: the runtime directories are
        # read directly, so without this projection a canonical token is served verbatim.
        with tempfile.TemporaryDirectory() as tmp:
            clone = self.tokenised_clone(Path(tmp))
            claude, codex = Path(tmp) / "claude", Path(tmp) / "codex"
            for harness, out in (("claude", claude), ("codex", codex)):
                result = self.run_in(clone, "install_skills.py", "--harness", harness, "--output-dir", out)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("instructions live in CLAUDE.md", (claude / TOKENISED).read_text())
            self.assertIn("instructions live in AGENTS.md", (codex / TOKENISED).read_text())
            # An untokenised skill is projected verbatim, not skipped.
            self.assertTrue((claude / "handoff" / "SKILL.md").is_file())
            # Repository machinery never reaches a runtime.
            for excluded in ("tools", "hooks", "generated", "policy", "README.md"):
                self.assertFalse((claude / excluded).exists(), excluded)

    def test_projection_refuses_to_erase_the_checkout(self) -> None:
        # rmtree on a caller-supplied path. The README advertises ~/.agents/skills as
        # the preferred checkout, so the runtime directory is the FIRST path anyone
        # points this at — and it holds tracked and untracked work.
        install = ADAPTERS / "install_skills.py"
        for target in (ROOT, ROOT.parent, ROOT / "skills" / "orchestration"):
            result = self.run_tool(install, "--harness", "claude", "--output-dir", target, "--allow-uncommitted-adapters")
            self.assertEqual(result.returncode, 1, f"{target} was not refused")
            self.assertTrue((ADAPTERS / "install_skills.py").is_file())
        # The canonical checkout is still intact after all three attempts.
        self.assertTrue((ROOT / "skills" / "orchestration" / "SKILL.md").is_file())

    def test_projection_refuses_a_directory_it_did_not_create(self) -> None:
        install = ADAPTERS / "install_skills.py"
        with tempfile.TemporaryDirectory() as tmp:
            occupied = Path(tmp) / "live-runtime"
            occupied.mkdir()
            (occupied / "local-work.md").write_text("unreviewed\n")
            result = self.run_tool(install, "--harness", "codex", "--output-dir", occupied, "--allow-uncommitted-adapters")
            self.assertEqual(result.returncode, 1)
            self.assertIn("refusing to replace", result.stderr)
            self.assertTrue((occupied / "local-work.md").is_file())
            # Its own previous output is reusable, so reruns still work.
            projection = Path(tmp) / "projection"
            self.assertEqual(
                self.run_tool(install, "--harness", "codex", "--output-dir", projection, "--allow-uncommitted-adapters").returncode,
                0,
            )
            self.assertEqual(
                self.run_tool(install, "--harness", "codex", "--output-dir", projection, "--allow-uncommitted-adapters").returncode,
                0,
            )

    def test_projection_refresh_refuses_to_delete_retained_content(self) -> None:
        # A marker proves the installer created the base projection; it does not make
        # local or provider-owned additions disposable. A runtime may deliberately retain
        # entries such as Codex's `.system`, so a routine refresh must stop before the
        # swap instead of silently replacing the union with canonical files alone.
        install = ADAPTERS / "install_skills.py"
        with tempfile.TemporaryDirectory() as tmp:
            projection = Path(tmp) / "projection"
            first = self.run_tool(
                install, "--harness", "codex", "--output-dir", projection,
                "--allow-uncommitted-adapters",
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            retained = projection / ".system" / "provider-skill" / "SKILL.md"
            retained.parent.mkdir(parents=True)
            retained.write_text("provider owned\n")

            refresh = self.run_tool(
                install, "--harness", "codex", "--output-dir", projection,
                "--allow-uncommitted-adapters",
            )

            self.assertEqual(refresh.returncode, 1, refresh.stdout)
            self.assertIn("would delete retained content", refresh.stderr)
            self.assertTrue(retained.is_file())
            self.assertEqual(retained.read_text(), "provider owned\n")
            self.assertFalse(any(projection.parent.glob(".skill-projection-previous-*")))

    def test_projection_carries_only_tracked_files(self) -> None:
        # rglob would sweep in .venv, node_modules and any untracked local credential.
        install = ADAPTERS / "install_skills.py"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "claude"
            self.assertEqual(
                self.run_tool(install, "--harness", "claude", "--output-dir", out, "--allow-uncommitted-adapters").returncode,
                0,
            )
            # The installer archives HEAD deliberately, so compare its output to the
            # same immutable tree rather than the mutable index. A staged addition or
            # deletion must not redefine what an installer run can publish.
            tracked_at_head = set(
                subprocess.run(
                    ["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", "HEAD:skills"],
                    text=True, capture_output=True, check=True,
                ).stdout.split()
            )
            for path in out.rglob("*"):
                if path.is_dir() or path.name == ".skill-projection":
                    continue
                self.assertIn(
                    str(path.relative_to(out)), tracked_at_head, f"{path} is not in HEAD"
                )

    def test_a_token_split_across_lines_is_rejected(self) -> None:
        # Whitespace in GraphQL-style templating includes newlines. Permitting only
        # spaces and tabs let `{{\nHARNESS_NAME\n}}` past discovery, rendering and the
        # install leak guard alike, so it shipped literally.
        import render_skills

        self.assertNotEqual(
            render_skills.malformed_tokens("see {{\nHARNESS_NAME\n}} here"), []
        )
        for harness in HARNESS_TOKENS:
            with self.assertRaises(ValueError):
                render_text("see {{\nHARNESS_NAME\n}} here", harness, "fixture.md")

    def test_projection_reads_the_commit_not_the_working_tree(self) -> None:
        # Listing tracked PATHS proved nothing about their CONTENT: the copy came from
        # the working tree, so a dirty checkout published unstaged edits — or a secret
        # pasted into a tracked file — straight into the runtime.
        install = ADAPTERS / "install_skills.py"
        victim = ROOT / "skills" / "handoff" / "SKILL.md"
        original = victim.read_text()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "projection"
            try:
                victim.write_text(original + "\nLEAKED_UNCOMMITTED_SECRET\n")
                self.assertEqual(
                    self.run_tool(install, "--harness", "claude", "--output-dir", out, "--allow-uncommitted-adapters").returncode,
                    0,
                )
                self.assertNotIn(
                    "LEAKED_UNCOMMITTED_SECRET",
                    (out / "handoff" / "SKILL.md").read_text(),
                    "an uncommitted working-tree edit reached the projection",
                )
            finally:
                victim.write_text(original)

    def test_punctuated_placeholder_names_are_rejected(self) -> None:
        # A typo introducing punctuation stopped the name matching AT ALL, so the
        # candidate never entered validation — a different failure from the whitespace
        # and brace-count cases, and one that shipped literal braces.
        import render_skills

        # Enumerating separators was itself the bug: a whitelist covers the punctuation
        # someone already typed, not the punctuation someone might. A space and a slash
        # are the same typo class as a hyphen and were missed by the first widening.
        for text in (
            "{{HARNESS-NAME}}",
            "{{HARNESS.NAME}}",
            "{{HARNESS:NAME}}",
            "{{HARNESS NAME}}",
            "{{HARNESS/NAME}}",
            "{{HARNESS\tNAME}}",
            "{{HARNESS*NAME}}",
            "{{HARNESS,NAME}}",
        ):
            self.assertNotEqual(
                render_skills.malformed_tokens(text), [], f"{text!r} was accepted"
            )
        # Every one of these is a real string from a tracked skill. They stay out of
        # scope because each carries a lowercase letter where a name segment would have
        # to begin — that, not the separator set, is what makes the wide class safe.
        for text in (
            "{{ .Site.Title }}",
            "{{date}}",
            '{{ partial "x" . }}',
            "{X.Y}",
            "{{Page URL}}",
            "{{system.page.url}}",
            "${{ secrets.DEPLOY_TOKEN }}",
            "{{< turnstile-form >}}",
            "{{ }}",
            "{{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}",
        ):
            self.assertEqual(
                render_skills.malformed_tokens(text), [], f"{text!r} was wrongly flagged"
            )
        # Trailing spacing must land in `trail`, not in the name, or the vocabulary
        # check misses and the single-brace rule lets a real token ship literally.
        self.assertNotEqual(render_skills.malformed_tokens("{HARNESS_NAME }"), [])

    def test_punctuation_between_the_name_and_the_closing_braces(self) -> None:
        # `_NAME` must end on a name character so trailing spacing lands in `trail`,
        # and `trail` only took whitespace — so a real token one stray character wide
        # matched NOTHING and shipped its braces. The edge groups now absorb any
        # non-name, non-brace run, which is the same reasoning that widened the
        # separator: what may appear there is not enumerable in advance.
        import render_skills

        for text in ("{{HARNESS_NAME.}}", "{{.HARNESS_NAME}}", "{{HARNESS_NAME!}}",
                     "{HARNESS_NAME.}", "{{HARNES_NAM.}}", '{{"HARNESS_NAME"}}'):
            self.assertNotEqual(
                render_skills.malformed_tokens(text), [], f"{text!r} was accepted"
            )
        # The corpus strings that live next to punctuation stay out of scope.
        for text in ("{{ .Site.Title }}", "{{ .Site.Params.turnstileSitekey }}",
                     "{{< turnstile-form >}}", '{{ partial "turnstile.html" . }}',
                     "{{Page URL}}", "${{ secrets.DEPLOY_TOKEN }}", "{{ }}"):
            self.assertEqual(
                render_skills.malformed_tokens(text), [], f"{text!r} was wrongly flagged"
            )

    def test_a_placeholder_whose_braces_are_never_closed(self) -> None:
        # BRACED_NAME_RE requires a closing run, so `{{HARNESS_NAME` matched nothing.
        # Making the closing OPTIONAL there is not the fix — `\}*` succeeds on empty, so
        # `{{Page URL}}` would match with the name `P` and be reported as malformed.
        # Hence a separate pattern with a maximal-name guard and a no-reachable-brace
        # guard, which is why the Zaraz case below is asserted right beside it.
        import render_skills

        for text in ("{{HARNESS_NAME", "{{ HARNESS_NAME", "{{2FA_SECRET", "{{HARNES_NAM"):
            self.assertNotEqual(
                render_skills.malformed_tokens(text), [], f"{text!r} was accepted"
            )
        for text in ("{{Page URL}}", "{{ .Site.Title }}", "{{< turnstile-form >}}",
                     "${{ secrets.DEPLOY_TOKEN }}", "{{ }}",
                     # Single braces keep their documentation exemption even unclosed;
                     # flagging them is the noise the exemption exists to avoid.
                     "{HARNESS_NAME"):
            self.assertEqual(
                render_skills.malformed_tokens(text), [], f"{text!r} was wrongly flagged"
            )
        # A well-formed-but-loose placeholder must be reported ONCE, by the braced
        # pattern — the unclosed pattern must not also claim it.
        self.assertEqual(render_skills.malformed_tokens("{{ HARNESS_NAME }}"), ["{{ HARNESS_NAME }}"])

    def test_the_leak_guard_uses_the_same_pattern_as_the_renderer(self) -> None:
        # A backstop narrower than the thing it backs reports clean on exactly the
        # spellings the renderer just learned to reject.
        import install_skills

        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp)
            (tree / "leaky.md").write_text("shipped {{HARNESS_NAME.}} here\n")
            self.assertIsNotNone(install_skills.leaked_tokens(tree, "claude"))
            (tree / "leaky.md").write_text("shipped {{ .Site.Title }} here\n")
            self.assertIsNone(install_skills.leaked_tokens(tree, "claude"))

    def test_malformed_names_starting_with_a_digit_or_underscore(self) -> None:
        # The candidate class must claim everything the STRICT class claims. Requiring
        # an uppercase letter first meant `{{2FA_SECRET}}` failed the build as an
        # unknown token while `{{ 2FA_SECRET }}` — the same name, written loosely —
        # matched nothing at all and shipped its braces.
        import render_skills

        for text in ("{{ 2FA_SECRET }}", "{{ _HARNESS_NAME }}", "{{2FA SECRET}}"):
            self.assertNotEqual(
                render_skills.malformed_tokens(text), [], f"{text!r} was accepted"
            )
        for harness in HARNESS_TOKENS:
            with self.assertRaises(KeyError):
                render_text("{{2FA_SECRET}}", harness, "fixture.md")
        # Single-brace documentation placeholders keep their exemption at every start.
        self.assertEqual(render_skills.malformed_tokens("{2FA_SECRET} and {_SLUG}"), [])

    def clean_clone(self, tmp: Path) -> Path:
        """A pristine checkout at HEAD — the state CI actually runs in.

        This test first asserted the refusal against the DEVELOPMENT tree, which is
        dirty by definition. That passed here and failed in CI, where both adapters
        match HEAD and the installer correctly succeeds: it was proving the state of
        my working tree, not the behaviour of the guard. A clone makes both the clean
        and the dirty case constructible, and neither one can touch this checkout.
        """
        checkout = tmp / "clean-checkout"
        subprocess.run(
            ["git", "clone", "--quiet", "--no-hardlinks", str(REPO_ROOT), str(checkout)],
            check=True, capture_output=True,
        )
        return checkout

    def tokenised_clone(self, tmp: Path) -> Path:
        """A clone carrying one skill that uses every token in the vocabulary.

        No SHIPPED skill carries a token today — every one that names a harness is
        either a Claude-scoped edition, a GSD skill bound to `$HOME/.claude/`, or a
        multi-harness install list where the name is a heading rather than a variable.
        That is a fact about the corpus, not about the renderer, so the renderer is
        exercised against a fixture and the corpus is checked separately.
        """
        clone = self.clean_clone(tmp)
        target = clone / "skills" / TOKENISED
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(TOKENISED_BODY)
        subprocess.run(["git", "-C", str(clone), "add", "-A"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(clone), "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-qm", "fixture"],
            check=True, capture_output=True,
        )
        return clone

    def run_in(self, clone: Path, tool: str, *args: str) -> subprocess.CompletedProcess[str]:
        """Run one of the clone's own adapters, so ROOT resolves to the clone."""
        return subprocess.run(
            ["python3", str(clone / "tools" / "adapters" / tool), *map(str, args)],
            cwd=clone, text=True, capture_output=True, check=False,
        )

    def render_all_in(self, clone: Path, out: Path) -> None:
        self.assertEqual(self.run_in(clone, "render_policy.py", "--output-dir", out).returncode, 0)
        result = self.run_in(clone, "render_skills.py", "--output-dir", out / "skills")
        self.assertEqual(result.returncode, 0, result.stderr)

    def install_from(self, clone: Path, out: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(clone / "tools" / "adapters" / "install_skills.py"),
             "--harness", "claude", "--output-dir", str(out)],
            cwd=clone, text=True, capture_output=True, check=False,
        )

    def test_projection_refuses_a_symlink_that_lands_in_the_checkout(self) -> None:
        # The guard resolved the path and the writes did not. A symlink INSIDE the
        # checkout pointing somewhere harmless therefore passed — and then
        # `mkdtemp(dir=output_dir.parent)` and `replace()` ran on the unresolved path,
        # putting the staging tree and the swap inside the canonical checkout.
        install = ADAPTERS / "install_skills.py"
        with tempfile.TemporaryDirectory() as tmp:
            elsewhere = Path(tmp) / "elsewhere"
            link = ROOT / ".projection-symlink-fixture"
            link.symlink_to(elsewhere, target_is_directory=True)
            try:
                result = self.run_tool(
                    install, "--harness", "claude", "--output-dir", link,
                    "--allow-uncommitted-adapters",
                )
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("canonical checkout", result.stderr)
                self.assertFalse(elsewhere.exists(), "a refused projection must write nothing")
                self.assertEqual(
                    list(ROOT.glob(".skill-projection-*")), [],
                    "staging must never be created inside the checkout",
                )
            finally:
                link.unlink()

    def test_projection_refuses_to_cross_harnesses_on_one_path(self) -> None:
        # The marker recorded `harness=` from the first version and nothing read it, so
        # owning the directory was treated as sufficient. Pointing a Codex install at a
        # Claude projection replaced a live runtime with the other harness's text and
        # exited 0 — a silent overwrite that looked like a successful install.
        with tempfile.TemporaryDirectory() as tmp:
            clone = self.tokenised_clone(Path(tmp))
            out = Path(tmp) / "projection"
            first = self.run_in(clone, "install_skills.py", "--harness", "claude", "--output-dir", out)
            self.assertEqual(first.returncode, 0, first.stderr)
            claude_text = (out / TOKENISED).read_text()

            crossed = self.run_in(clone, "install_skills.py", "--harness", "codex", "--output-dir", out)
            self.assertEqual(crossed.returncode, 1, crossed.stdout)
            self.assertIn("is a claude projection", crossed.stderr)
            # Refused means untouched, not half-replaced.
            self.assertEqual((out / TOKENISED).read_text(), claude_text)
            self.assertIn("harness=claude", (out / MARKER_NAME).read_text())

            # Re-projecting the SAME harness onto its own path stays allowed — the rule
            # is one path per harness, not one install per path.
            again = self.run_in(clone, "install_skills.py", "--harness", "claude", "--output-dir", out)
            self.assertEqual(again.returncode, 0, again.stderr)

    def test_projection_accepts_committed_rendering_logic(self) -> None:
        # The other half of the guard: default-on must still mean "runs on a clean
        # checkout". Without this, tightening the refusal into an unconditional one
        # would look green.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "projection"
            result = self.install_from(self.clean_clone(Path(tmp)), out)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((out / ".skill-projection").is_file())

    def test_projection_refuses_uncommitted_rendering_logic(self) -> None:
        # Archiving the SOURCES from HEAD does not make the projection reviewed: a local
        # edit to the token mapping changes what is published without changing any
        # archived file.
        with tempfile.TemporaryDirectory() as tmp:
            clone = self.clean_clone(Path(tmp))
            adapter = clone / "tools" / "adapters" / "render_skills.py"
            adapter.write_bytes(adapter.read_bytes() + b'\nHARNESS_TOKENS["claude"] = {}\n')
            out = Path(tmp) / "projection"
            result = self.install_from(clone, out)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("uncommitted rendering logic", result.stderr)
            self.assertIn("adapters/render_skills.py", result.stderr)
            self.assertFalse(out.exists(), "a refused projection must write nothing")

    def test_projection_refuses_to_ship_a_token(self) -> None:
        install = ADAPTERS / "install_skills.py"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "claude"
            self.assertEqual(
                self.run_tool(install, "--harness", "claude", "--output-dir", out, "--allow-uncommitted-adapters").returncode,
                0,
            )
            for path in out.rglob("*.md"):
                for token in HARNESS_TOKENS["claude"]:
                    self.assertNotIn("{{" + token + "}}", path.read_text(), str(path))

    def test_every_tokenised_source_renders_for_every_harness(self) -> None:
        # Deliberately NOT asserting that at least one exists. It did once, and the
        # assertion is what kept a token alive in a file that should never have had
        # one — twice. Whether a shipped skill SHOULD carry a token is a judgement
        # about that skill, and forcing the corpus to satisfy a test is how the wrong
        # judgement gets made. The renderer's own behaviour is covered by fixtures.
        for source in skill_sources():
            for harness in HARNESS_TOKENS:
                render_text(source.read_text(), harness, str(source))

    def test_no_shipped_skill_currently_needs_a_harness_token(self) -> None:
        # Today the answer is none: clean-my-ai-harness names both harnesses in its own
        # text, and every other skill here is harness-neutral prose. This asserts the
        # state rather than the rule, so
        # the day a genuinely portable skill wants a token, this test fails and the
        # judgement gets made deliberately instead of by accident.
        self.assertEqual(
            [str(p.relative_to(ROOT / "skills")) for p in skill_sources()], [],
            "a skill now carries a harness token — confirm the whole FILE is portable, "
            "not just the sentence, before accepting it here",
        )

    def test_check_reports_a_drifted_skill_rendering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clone, out = self.tokenised_clone(Path(tmp)), Path(tmp) / "generated"
            self.render_all_in(clone, out)
            target = out / "skills" / "codex" / TOKENISED
            target.write_text(target.read_text().replace("AGENTS.md", "CLAUDE.md", 1))
            result = self.run_in(clone, "check_generation.py", "--output-dir", out)
            self.assertEqual(result.returncode, 1)
            self.assertIn("differs from canonical source", result.stderr)

    def test_check_reports_a_missing_skill_rendering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clone, out = self.tokenised_clone(Path(tmp)), Path(tmp) / "generated"
            self.render_all_in(clone, out)
            (out / "skills" / "claude" / TOKENISED).unlink()
            result = self.run_in(clone, "check_generation.py", "--output-dir", out)
            self.assertEqual(result.returncode, 1)
            self.assertIn("missing", result.stderr)

    def test_check_reports_a_stale_rendering_of_an_untokenised_source(self) -> None:
        # A source that stops using tokens must stop being rendered, or the install
        # overlay keeps applying a file canonical no longer knows about.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.render_all(out)
            orphan = out / "skills" / "codex" / "retired-skill" / "SKILL.md"
            orphan.parent.mkdir(parents=True, exist_ok=True)
            orphan.write_text("left behind\n")
            result = self.run_tool(CHECK, "--output-dir", out)
            self.assertEqual(result.returncode, 1)
            self.assertIn("no longer tokenised", result.stderr)

    def test_check_accepts_exact_renderings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.render_all(out)
            result = self.run_tool(CHECK, "--output-dir", out)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_committed_renderings_are_current(self) -> None:
        # The gate CI actually runs: the tree in generated/ must match the sources.
        result = self.run_tool(CHECK)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
