#!/usr/bin/env python3
"""Validate evals/_factory/golden.json against the schema."""

import json
import re
import sys
from pathlib import Path

VALID_KINDS = {
    "non_address",
    "exact_within_50km",
    "exact_outside_50km",
    "multiple_matches",
    "not_found",
    "missing_door_number",
    "partial_match",
    "adversarial_profanity",
    "multilingual",
}
VALID_SPLITS = {"dev", "test"}
VALID_DIRECTIVES = {"CONTINUE", "HALT_NON_ADDRESS"}
VALID_CLARIFICATION_REASONS = {
    None,
    "MULTIPLE_MATCHES",
    "ADDRESS_NOT_FOUND",
    "PARTIAL_MATCH",
    "MISSING_PREMISE_NUMBER",
    "PREMISE_NUMBER_UNVERIFIED",
    "NO_USABLE_ROUTE",
}


def validate_golden(golden_path: Path) -> list[str]:
    """Return a list of validation errors (empty means valid)."""
    errors: list[str] = []
    if not golden_path.exists():
        return [f"Missing golden file: {golden_path}"]

    try:
        cases = json.loads(golden_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"Invalid JSON in {golden_path}: {exc}"]

    if not isinstance(cases, list) or not cases:
        return ["golden.json must be a non-empty JSON array"]

    seen_ids: set[str] = set()
    for idx, case in enumerate(cases):
        prefix = f"row[{idx}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix}: must be an object")
            continue

        cid = case.get("id")
        if not isinstance(cid, str) or not cid.strip():
            errors.append(f"{prefix}: missing non-empty string 'id'")
        elif cid in seen_ids:
            errors.append(f"{prefix}: duplicate id {cid!r}")
        else:
            seen_ids.add(cid)
            prefix = f"{cid}"

        if case.get("kind") not in VALID_KINDS:
            errors.append(f"{prefix}: invalid kind {case.get('kind')!r}")
        if case.get("split") not in VALID_SPLITS:
            errors.append(f"{prefix}: invalid split {case.get('split')!r}")
        if not isinstance(case.get("input"), str) or not case["input"].strip():
            errors.append(f"{prefix}: missing non-empty 'input'")
        if not isinstance(case.get("notes"), str) or not case["notes"].strip():
            errors.append(f"{prefix}: missing non-empty 'notes'")

        exp01 = case.get("expected_input")
        if not isinstance(exp01, dict):
            errors.append(f"{prefix}: 'expected_input' must be an object")
        else:
            if not isinstance(exp01.get("is_address"), bool):
                errors.append(f"{prefix}: expected_input.is_address must be boolean")

        exp03 = case.get("expected_orientation")
        if exp03 is not None:
            if not isinstance(exp03, dict):
                errors.append(f"{prefix}: 'expected_orientation' must be null or an object")
            elif "clarification_reason" in exp03:
                reason = exp03["clarification_reason"]
                if reason not in VALID_CLARIFICATION_REASONS:
                    errors.append(f"{prefix}: invalid clarification_reason {reason!r}")

        for field in ("exp_message_must_contain", "exp_message_must_not"):
            patterns = case.get(field)
            if patterns is None:
                continue
            if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
                errors.append(f"{prefix}: {field} must be a list of regex strings")
                continue
            for pat in patterns:
                try:
                    re.compile(pat, re.IGNORECASE)
                except re.error as exc:
                    errors.append(f"{prefix}: invalid regex in {field} ({pat!r}): {exc}")

    return errors


def main() -> int:
    golden_path = Path(__file__).resolve().parent.parent / "golden.json"
    errors = validate_golden(golden_path)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    cases = json.loads(golden_path.read_text(encoding="utf-8"))
    print(f"OK: {len(cases)} golden cases validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
