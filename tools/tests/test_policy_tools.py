import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = ROOT / "tools" / "adapters"
RENDER = ADAPTERS / "render_policy.py"
RENDER_SKILLS = ADAPTERS / "render_skills.py"
CHECK = ADAPTERS / "check_generation.py"
sys.path.insert(0, str(ROOT / "tools"))


class PolicyToolsTests(unittest.TestCase):
    def run_tool(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", *map(str, args)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_rendered_harnesses_share_governance_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = self.run_tool(RENDER, "--output-dir", out)
            self.assertEqual(result.returncode, 0, result.stderr)

            claude = (out / "CLAUDE.md").read_text()
            codex = (out / "AGENTS.md").read_text()
            for contract in (
                "Write collision",
                "Non-isolatable decision",
                "External proof boundary",
                "one mutation owner",
                "operator-started interactive session",
                "implicit authorization",
                "available operator or administrator capability",
                "no second approval",
            ):
                self.assertIn(contract, claude)
                self.assertIn(contract, codex)
            for rendered in (claude, codex):
                self.assertIn("Unattended automation", rendered)
                self.assertIn("accepted ticket", rendered)
                self.assertIn("outcome, named targets, and Done conditions", rendered)
                self.assertIn("never authorizes adjacent work", rendered)
            self.assertRegex(claude, r"Policy generation: `[0-9a-f]{64}`")
            self.assertRegex(codex, r"Policy generation: `[0-9a-f]{64}`")

    def test_rendered_harnesses_share_the_ai_code_review_standard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = self.run_tool(RENDER, "--output-dir", out)
            self.assertEqual(result.returncode, 0, result.stderr)

            for filename in ("CLAUDE.md", "AGENTS.md"):
                rendered = (out / filename).read_text()
                for contract in (
                    "# AI code review standard",
                    "A clean review is a valid and useful result.",
                    "## Elevated review",
                    "Higher model effort may inspect more code.",
                    "one primary maintainer",
                    "Respect the declared source of truth.",
                    "## Receipt",
                    "base revision, and head revision",
                ):
                    self.assertIn(contract, rendered)

    def test_rendered_harnesses_route_browsers_by_use_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = self.run_tool(RENDER, "--output-dir", out)
            self.assertEqual(result.returncode, 0, result.stderr)

            for filename in ("CLAUDE.md", "AGENTS.md"):
                rendered = (out / filename).read_text()
                for contract in (
                    "harness preview",
                    "operator-present",
                    "managed Playwright",
                    "ephemeral browser context",
                    "persistent service profile",
                    "Playwright MCP",
                    "personal browser profile",
                ):
                    self.assertIn(contract, rendered)

    def test_harness_specific_policy_limits_personal_chrome_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = self.run_tool(RENDER, "--output-dir", out)
            self.assertEqual(result.returncode, 0, result.stderr)

            claude = (out / "CLAUDE.md").read_text()
            codex = (out / "AGENTS.md").read_text()
            for contract in ("--no-chrome", "--chrome", "Claude-in-Chrome"):
                self.assertIn(contract, claude)
            for contract in ("Computer Use", "managed Playwright"):
                self.assertIn(contract, codex)

    def test_check_reports_a_drifted_rendering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            rendered = self.run_tool(RENDER, "--output-dir", out)
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            with (out / "AGENTS.md").open("a") as handle:
                handle.write("\nlocal drift\n")

            checked = self.run_tool(CHECK, "--output-dir", out)
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("AGENTS.md differs", checked.stderr)

    def test_check_accepts_exact_renderings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            rendered = self.run_tool(RENDER, "--output-dir", out)
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            # check_generation gates policy AND skill renderings, so a half-rendered
            # tree is a genuine failure rather than a test-setup detail.
            skills = self.run_tool(RENDER_SKILLS, "--output-dir", out / "skills")
            self.assertEqual(skills.returncode, 0, skills.stderr)
            checked = self.run_tool(CHECK, "--output-dir", out)
            self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_check_reports_a_policy_rendering_without_its_skills(self) -> None:
        # Built in a CLONE carrying a tokenised fixture skill, because no shipped skill
        # carries a token: against the real corpus there is no skill rendering to be
        # missing, so this passed vacuously and proved nothing about the wiring.
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / "checkout"
            subprocess.run(
                ["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(clone)],
                check=True, capture_output=True,
            )
            fixture = clone / "skills" / "token-fixture" / "SKILL.md"
            fixture.parent.mkdir(parents=True, exist_ok=True)
            fixture.write_text("Runs on {{HARNESS_NAME}}.\n")
            subprocess.run(["git", "-C", str(clone), "add", "-A"], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(clone), "-c", "user.email=t@t", "-c", "user.name=t",
                 "commit", "-qm", "fixture"],
                check=True, capture_output=True,
            )
            out = Path(tmp) / "generated"
            adapters = clone / "tools" / "adapters"
            rendered = subprocess.run(
                ["python3", str(adapters / "render_policy.py"), "--output-dir", str(out)],
                cwd=clone, text=True, capture_output=True, check=False,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            checked = subprocess.run(
                ["python3", str(adapters / "check_generation.py"), "--output-dir", str(out)],
                cwd=clone, text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("missing", checked.stderr)

    def test_preflight_accepts_clean_current_exact_install(self) -> None:
        from adapters.preflight import failures, inspect

        with patch("adapters.preflight.git", side_effect=["", "same", "same"]):
            report = inspect(
                ROOT, ROOT / "generated" / "CLAUDE.md", ROOT / "generated" / "AGENTS.md"
            )
        self.assertEqual(failures(report), [])

    def test_preflight_rejects_dirty_or_stale_checkout(self) -> None:
        from adapters.preflight import failures, inspect

        with patch("adapters.preflight.git", side_effect=["M policy/universal.md", "old", "new"]):
            report = inspect(
                ROOT, ROOT / "generated" / "CLAUDE.md", ROOT / "generated" / "AGENTS.md"
            )
        self.assertIn("canonical checkout is dirty", failures(report))
        self.assertIn("canonical checkout is not exactly at remote main", failures(report))

    def test_wave_brief_carries_shared_contract_invalidation(self) -> None:
        brief = (ROOT / "skills" / "orchestration" / "references" / "wave-brief.md").read_text()
        for phrase in ("contract decision owner", "permitted writer", "integration owner", "epoch"):
            self.assertIn(phrase, brief)

    def test_preflight_rejects_repository_generation_mismatch(self) -> None:
        from adapters.preflight import failures, inspect

        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "marker.json"
            marker.write_text(json.dumps({"expected_generation": "0" * 64}))
            with patch("adapters.preflight.git", side_effect=["", "same", "same"]):
                report = inspect(
                    ROOT, ROOT / "generated" / "CLAUDE.md",
                    ROOT / "generated" / "AGENTS.md", marker
                )
        self.assertIn("repository expects a different global policy generation", failures(report))


if __name__ == "__main__":
    unittest.main()
