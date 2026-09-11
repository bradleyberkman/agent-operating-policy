#!/usr/bin/env python3
"""Validate cross-harness skill evidence and build an offline usefulness report.

This module performs no discovery, network access, or collection by default. A
caller must supply already-observed configuration/exposure evidence and an
explicitly enabled minimal invocation receipt.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import stat
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
SOURCE_KINDS = {"repository", "local-root", "system", "symlink", "plugin"}
CONFIGURATION_STATES = {"enabled", "disabled", "not-applicable", "unknown"}
EXPOSURE_STATES = {"exposed", "not-exposed", "unknown"}
CALLER_CLASSES = {"human", "agent", "automation", "test", "unknown"}
SURFACES = {
    "claude": {"claude-ai", "claude-code", "anthropic-api", "unknown-claude-surface"},
    "codex": {"codex-cli", "codex-app", "openai-api", "unknown-codex-surface"},
}
SURFACE_FIELDS = {"schema_version", "surfaces"}
SURFACE_RECORD_FIELDS = {"harness", "surface", "skills"}
SKILL_REQUIRED_FIELDS = {
    "catalog_id",
    "provider_identity",
    "callable_name",
    "source_kind",
    "source_ref",
    "configuration_state",
    "exposure_state",
}
SKILL_OPTIONAL_FIELDS = {"symlink_target"}
RECEIPT_FIELDS = {
    "schema_version",
    "harness",
    "provider_identity",
    "callable_name",
    "timestamp",
    "caller_class",
}
SAFE_IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/+\-]{0,199}$")
UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")


class EvidenceError(ValueError):
    """Raised when evidence violates the portable privacy contract."""


class CollectionDisabled(EvidenceError):
    """Raised when receipt collection was not explicitly enabled."""


def _exact_fields(value: dict[str, Any], expected: set[str], label: str) -> None:
    extra = set(value) - expected
    missing = expected - set(value)
    if extra:
        raise EvidenceError(f"{label} has unexpected fields: {sorted(extra)}")
    if missing:
        raise EvidenceError(f"{label} is missing fields: {sorted(missing)}")


def _identity(value: object, label: str) -> str:
    if not isinstance(value, str) or not SAFE_IDENTITY.fullmatch(value):
        raise EvidenceError(f"{label} must be a bounded portable identity")
    return value


def _portable_ref(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 500:
        raise EvidenceError(f"{label} must be a non-empty portable reference")
    if value.startswith(("/", "~")) or "\\" in value or any(ord(char) < 32 for char in value):
        raise EvidenceError(f"{label} must be portable and must not expose an absolute path")
    if ".." in PurePosixPath(value).parts:
        raise EvidenceError(f"{label} must be portable and cannot traverse parents")
    return value


def validate_surface_evidence(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise EvidenceError("surface evidence must be an object")
    _exact_fields(payload, SURFACE_FIELDS, "surface evidence")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise EvidenceError(f"schema_version must be {SCHEMA_VERSION}")
    surfaces = payload["surfaces"]
    if not isinstance(surfaces, list) or not surfaces:
        raise EvidenceError("surfaces must be a non-empty list")
    seen_surfaces: set[tuple[str, str]] = set()
    for surface_index, surface in enumerate(surfaces):
        label = f"surfaces[{surface_index}]"
        if not isinstance(surface, dict):
            raise EvidenceError(f"{label} must be an object")
        _exact_fields(surface, SURFACE_RECORD_FIELDS, label)
        harness = surface["harness"]
        if harness not in SURFACES:
            raise EvidenceError(f"{label}.harness must be claude or codex")
        if surface["surface"] not in SURFACES[harness]:
            raise EvidenceError(f"{label}.surface is invalid for {harness}")
        surface_identity = (harness, surface["surface"])
        if surface_identity in seen_surfaces:
            raise EvidenceError(f"duplicate surface: {surface_identity}")
        seen_surfaces.add(surface_identity)
        skills = surface["skills"]
        if not isinstance(skills, list):
            raise EvidenceError(f"{label}.skills must be a list")
        seen_skills: set[tuple[str, str]] = set()
        for skill_index, skill in enumerate(skills):
            skill_label = f"{label}.skills[{skill_index}]"
            if not isinstance(skill, dict):
                raise EvidenceError(f"{skill_label} must be an object")
            allowed = SKILL_REQUIRED_FIELDS | SKILL_OPTIONAL_FIELDS
            extra = set(skill) - allowed
            missing = SKILL_REQUIRED_FIELDS - set(skill)
            if extra:
                raise EvidenceError(f"{skill_label} has unexpected fields: {sorted(extra)}")
            if missing:
                raise EvidenceError(f"{skill_label} is missing fields: {sorted(missing)}")
            _identity(skill["catalog_id"], f"{skill_label}.catalog_id")
            provider = _identity(skill["provider_identity"], f"{skill_label}.provider_identity")
            callable_name = _identity(skill["callable_name"], f"{skill_label}.callable_name")
            _portable_ref(skill["source_ref"], f"{skill_label}.source_ref")
            if skill["source_kind"] not in SOURCE_KINDS:
                raise EvidenceError(f"{skill_label}.source_kind is invalid")
            if skill["configuration_state"] not in CONFIGURATION_STATES:
                raise EvidenceError(f"{skill_label}.configuration_state is invalid")
            if skill["exposure_state"] not in EXPOSURE_STATES:
                raise EvidenceError(f"{skill_label}.exposure_state is invalid")
            if skill["source_kind"] == "symlink":
                _identity(skill.get("symlink_target"), f"{skill_label}.symlink_target")
            elif "symlink_target" in skill:
                raise EvidenceError(f"{skill_label}.symlink_target is valid only for symlinks")
            identity = (provider, callable_name)
            if identity in seen_skills:
                raise EvidenceError(f"duplicate skill identity on {surface_identity}: {identity}")
            seen_skills.add(identity)
    return payload


def load_surface_evidence(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"could not read surface evidence: {exc.__class__.__name__}") from exc
    return validate_surface_evidence(payload)


def validate_invocation_receipt(receipt: object) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise EvidenceError("invocation receipt must be an object")
    _exact_fields(receipt, RECEIPT_FIELDS, "invocation receipt")
    if receipt["schema_version"] != SCHEMA_VERSION:
        raise EvidenceError(f"schema_version must be {SCHEMA_VERSION}")
    if receipt["harness"] not in SURFACES:
        raise EvidenceError("receipt harness must be claude or codex")
    _identity(receipt["provider_identity"], "provider_identity")
    _identity(receipt["callable_name"], "callable_name")
    timestamp = receipt["timestamp"]
    if not isinstance(timestamp, str) or not UTC_TIMESTAMP.fullmatch(timestamp):
        raise EvidenceError("timestamp must be an RFC3339 UTC value ending in Z")
    try:
        datetime.fromisoformat(timestamp.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise EvidenceError("timestamp is not a real UTC date-time") from exc
    if receipt["caller_class"] not in CALLER_CLASSES:
        raise EvidenceError(f"caller_class must be one of {sorted(CALLER_CLASSES)}")
    return receipt


def load_invocation_receipts(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EvidenceError(f"could not read invocation receipts: {exc.__class__.__name__}") from exc
    receipts: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            receipt = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvidenceError(f"invalid receipt JSON on line {line_number}") from exc
        receipts.append(validate_invocation_receipt(receipt))
    return receipts


def record_invocation(
    output: Path,
    receipt: dict[str, Any],
    *,
    enable_collection: bool = False,
) -> None:
    if not enable_collection:
        raise CollectionDisabled("invocation collection is dormant; explicit enablement is required")
    validate_invocation_receipt(receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(output, flags, 0o600)
    try:
        mode = stat.S_IMODE(os.fstat(descriptor).st_mode)
        if mode != 0o600:
            os.fchmod(descriptor, 0o600)
        payload = json.dumps(receipt, separators=(",", ":"), sort_keys=True) + "\n"
        os.write(descriptor, payload.encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _summary_state(states: set[str], preferred: tuple[str, ...]) -> str:
    for state in preferred:
        if state in states:
            return state
    return "unknown"


def build_offline_report(
    catalog_path: Path,
    surface_path: Path,
    receipts_path: Path,
    *,
    data_scope: str = "offline-files-only",
) -> dict[str, Any]:
    surfaces = load_surface_evidence(surface_path)
    receipts = load_invocation_receipts(receipts_path)
    with catalog_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if not reader.fieldnames or not {"catalog_id", "skill", "verdict"}.issubset(reader.fieldnames):
            raise EvidenceError("catalog must contain catalog_id, skill, and verdict")
        catalog = list(reader)

    evidence_by_catalog: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    lookup: dict[tuple[str, str, str], str] = {}
    for surface in surfaces["surfaces"]:
        harness = surface["harness"]
        for skill in surface["skills"]:
            evidence_by_catalog[skill["catalog_id"]].append((harness, skill))
            lookup[(harness, skill["provider_identity"], skill["callable_name"])] = skill["catalog_id"]

    receipts_by_catalog: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unmatched_receipts: list[dict[str, str]] = []
    for receipt in receipts:
        key = (receipt["harness"], receipt["provider_identity"], receipt["callable_name"])
        catalog_id = lookup.get(key)
        if catalog_id is None:
            unmatched_receipts.append(
                {
                    "harness": receipt["harness"],
                    "provider_identity": receipt["provider_identity"],
                    "callable_name": receipt["callable_name"],
                }
            )
            continue
        receipts_by_catalog[catalog_id].append(receipt)

    rows: list[dict[str, Any]] = []
    for catalog_row in catalog:
        catalog_id = catalog_row["catalog_id"]
        skill_evidence = evidence_by_catalog.get(catalog_id, [])
        if not skill_evidence:
            continue
        matched_receipts = receipts_by_catalog.get(catalog_id, [])
        configuration = _summary_state(
            {skill["configuration_state"] for _, skill in skill_evidence},
            ("enabled", "disabled", "not-applicable", "unknown"),
        )
        exposure = _summary_state(
            {skill["exposure_state"] for _, skill in skill_evidence},
            ("exposed", "not-exposed", "unknown"),
        )
        current = catalog_row["verdict"]
        reclassified = "PROBATION" if current == "INVESTIGATE" and matched_receipts else current
        reason = (
            "A minimal receipt proves at least one caller, but not usefulness or acceptance."
            if reclassified == "PROBATION" and current == "INVESTIGATE"
            else "No deterministic verdict transition is supported by the supplied evidence."
        )
        rows.append(
            {
                "catalog_id": catalog_id,
                "skill": catalog_row["skill"],
                "harnesses": sorted({harness for harness, _ in skill_evidence}),
                "provider_identities": sorted({skill["provider_identity"] for _, skill in skill_evidence}),
                "configuration_state": configuration,
                "exposure_state": exposure,
                "invocation_count": len(matched_receipts),
                "caller_classes": sorted({receipt["caller_class"] for receipt in matched_receipts}),
                "last_invoked_at": max((receipt["timestamp"] for receipt in matched_receipts), default=None),
                "current_verdict": current,
                "reclassified_verdict": reclassified,
                "reclassification_reason": reason,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "data_scope": _portable_ref(data_scope, "data_scope"),
        "network_access": False,
        "collection_enabled_by_default": False,
        "rows": rows,
        "unmatched_receipts": unmatched_receipts,
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    surface_parser = subparsers.add_parser("validate-surfaces")
    surface_parser.add_argument("evidence", type=Path)

    receipt_parser = subparsers.add_parser("validate-receipts")
    receipt_parser.add_argument("receipts", type=Path)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("catalog", type=Path)
    report_parser.add_argument("surfaces", type=Path)
    report_parser.add_argument("receipts", type=Path)
    report_parser.add_argument("--data-scope", default="offline-files-only")
    report_parser.add_argument("--output", type=Path)

    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("output", type=Path)
    record_parser.add_argument("--harness", choices=sorted(SURFACES), required=True)
    record_parser.add_argument("--provider-identity", required=True)
    record_parser.add_argument("--callable-name", required=True)
    record_parser.add_argument("--timestamp", default=None)
    record_parser.add_argument("--caller-class", choices=sorted(CALLER_CLASSES), required=True)
    record_parser.add_argument("--enable-collection", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "validate-surfaces":
            payload = load_surface_evidence(args.evidence)
            result: object = {"valid": True, "surfaces": len(payload["surfaces"])}
        elif args.command == "validate-receipts":
            receipts = load_invocation_receipts(args.receipts)
            result = {"valid": True, "receipts": len(receipts)}
        elif args.command == "report":
            result = build_offline_report(
                args.catalog,
                args.surfaces,
                args.receipts,
                data_scope=args.data_scope,
            )
            if args.output:
                _atomic_write_json(args.output, result)
                result = {"written": args.output.as_posix(), "rows": len(result["rows"])}
        else:
            receipt = {
                "schema_version": SCHEMA_VERSION,
                "harness": args.harness,
                "provider_identity": args.provider_identity,
                "callable_name": args.callable_name,
                "timestamp": args.timestamp or _utc_now(),
                "caller_class": args.caller_class,
            }
            record_invocation(
                args.output,
                receipt,
                enable_collection=args.enable_collection,
            )
            result = {"recorded": True, "output": args.output.as_posix()}
    except (EvidenceError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
