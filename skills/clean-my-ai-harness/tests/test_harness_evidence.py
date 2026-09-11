from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import harness_evidence as evidence
import scan_visible_harness as scanner


class HarnessSurfaceEvidenceTests(unittest.TestCase):
    def test_schemas_pin_cross_harness_origins_and_minimal_receipt_fields(self) -> None:
        surface_schema = json.loads(
            (SKILL_ROOT / "assets/harness-surface-evidence.schema.json").read_text()
        )
        skill_schema = surface_schema["$defs"]["skill"]
        self.assertFalse(skill_schema["additionalProperties"])
        self.assertEqual(
            set(skill_schema["properties"]["source_kind"]["enum"]),
            {"repository", "local-root", "system", "symlink", "plugin"},
        )
        self.assertEqual(
            set(surface_schema["$defs"]["surface"]["properties"]["harness"]["enum"]),
            {"claude", "codex"},
        )

        receipt_schema = json.loads(
            (SKILL_ROOT / "assets/skill-invocation-receipt.schema.json").read_text()
        )
        self.assertFalse(receipt_schema["additionalProperties"])
        self.assertEqual(set(receipt_schema["required"]), evidence.RECEIPT_FIELDS)
        self.assertNotIn("prompt", receipt_schema["properties"])
        self.assertNotIn("tool_payload", receipt_schema["properties"])

    def test_fixture_represents_every_origin_for_both_harnesses(self) -> None:
        payload = evidence.load_surface_evidence(
            FIXTURES / "cross-harness-surfaces.json"
        )
        expected = {"repository", "local-root", "system", "symlink", "plugin"}
        by_harness = {
            surface["harness"]: {skill["source_kind"] for skill in surface["skills"]}
            for surface in payload["surfaces"]
        }
        self.assertEqual(by_harness, {"claude": expected, "codex": expected})

    def test_surface_parser_rejects_absolute_paths_and_unbound_symlinks(self) -> None:
        payload = json.loads(
            (FIXTURES / "cross-harness-surfaces.json").read_text()
        )
        absolute = copy.deepcopy(payload)
        absolute["surfaces"][0]["skills"][0]["source_ref"] = "/Users/example/skill"
        with self.assertRaisesRegex(evidence.EvidenceError, "portable"):
            evidence.validate_surface_evidence(absolute)

        unbound = copy.deepcopy(payload)
        del unbound["surfaces"][1]["skills"][3]["symlink_target"]
        with self.assertRaisesRegex(evidence.EvidenceError, "symlink_target"):
            evidence.validate_surface_evidence(unbound)

    def test_scanner_carries_validated_skill_surface_evidence_into_both_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "target"
            target.mkdir()
            (target / "AGENTS.md").write_text("fixture\n")
            scope, harness_map = scanner.scan_visible_harness(
                target,
                surface="codex-cli",
                model="fixture-model",
                skill_evidence=FIXTURES / "cross-harness-surfaces.json",
            )
        self.assertEqual(
            scope["skill_surface_evidence"], harness_map["skill_surface_evidence"]
        )
        self.assertEqual(len(scope["skill_surface_evidence"]["surfaces"]), 2)


class InvocationReceiptTests(unittest.TestCase):
    def test_receipts_are_minimal_provider_aware_records(self) -> None:
        receipts = evidence.load_invocation_receipts(
            FIXTURES / "invocation-receipts.jsonl"
        )
        self.assertEqual(len(receipts), 2)
        self.assertEqual(
            set(receipts[0]),
            {
                "schema_version",
                "harness",
                "provider_identity",
                "callable_name",
                "timestamp",
                "caller_class",
            },
        )

        leaked = dict(receipts[0], prompt="private prompt")
        with self.assertRaisesRegex(evidence.EvidenceError, "unexpected"):
            evidence.validate_invocation_receipt(leaked)

    def test_collection_is_disabled_unless_the_caller_explicitly_enables_it(self) -> None:
        receipt = evidence.load_invocation_receipts(
            FIXTURES / "invocation-receipts.jsonl"
        )[0]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "receipts.jsonl"
            with self.assertRaises(evidence.CollectionDisabled):
                evidence.record_invocation(output, receipt)
            self.assertFalse(output.exists())
            evidence.record_invocation(output, receipt, enable_collection=True)
            self.assertEqual(evidence.load_invocation_receipts(output), [receipt])
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)


class OfflineUsefulnessReportTests(unittest.TestCase):
    def test_join_reclassifies_invoked_investigate_row_without_live_data(self) -> None:
        report = evidence.build_offline_report(
            FIXTURES / "investigate-catalog.tsv",
            FIXTURES / "cross-harness-surfaces.json",
            FIXTURES / "invocation-receipts.jsonl",
            data_scope="offline-fixtures-only",
        )
        self.assertFalse(report["collection_enabled_by_default"])
        self.assertEqual(report["data_scope"], "offline-fixtures-only")
        row = report["rows"][0]
        self.assertEqual(row["catalog_id"], "plugin:sites:building")
        self.assertEqual(row["configuration_state"], "enabled")
        self.assertEqual(row["exposure_state"], "exposed")
        self.assertEqual(row["invocation_count"], 1)
        self.assertEqual(row["current_verdict"], "INVESTIGATE")
        self.assertEqual(row["reclassified_verdict"], "PROBATION")
        self.assertNotIn("prompt", json.dumps(report).lower())
        self.assertNotIn("tool_payload", json.dumps(report).lower())


if __name__ == "__main__":
    unittest.main()
