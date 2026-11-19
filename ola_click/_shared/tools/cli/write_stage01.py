#!/usr/bin/env python3
"""Stage 01 finalizer: validate and write stage01_intent.json with conditional pipeline mapping."""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

VALID_ACTORS = {"customer", "owner", "unknown"}

INTENT_TO_PIPELINE: dict[str, str] = {
    # order_create
    "create_order": "order_create",
    # order_modify
    "update_order": "order_modify",
    "cancel_order": "order_modify",
    "advance_order_status": "order_modify",
    "apply_coupon_or_promo": "order_modify",
    "register_payment": "order_modify",
    # menu_read
    "check_menu_item": "menu_read",
    "get_menu_category": "menu_read",
    "check_store_hours_or_open": "menu_read",
    # menu_manage
    "set_item_out_of_stock": "menu_manage",
    "restore_item_in_stock": "menu_manage",
    "edit_menu": "menu_manage",
    # promotions
    "manage_promotions": "promotions",
    # logistics_delivery
    "quote_delivery": "logistics_delivery",
    "assign_rider": "logistics_delivery",
    "update_delivery_status": "logistics_delivery",
    "report_rider_position": "logistics_delivery",
    # backoffice_ops
    "check_order_status": "backoffice_ops",
    "list_active_orders": "backoffice_ops",
    "sales_summary": "backoffice_ops",
    "manage_customer_address": "backoffice_ops",
    # gates
    "non_actionable": "gate",
    "unsupported_request": "gate",
}

VALID_INTENTS = set(INTENT_TO_PIPELINE.keys())


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_run_dir(out_dir: str | None, start: bool) -> tuple[str, Path]:
    if out_dir:
        p = Path(out_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p.name, p

    state_dir = Path(tempfile.gettempdir()) / "olaclick-icm"
    state_dir.mkdir(parents=True, exist_ok=True)
    active_file = state_dir / ".active-run"

    if start or not active_file.is_file():
        stamp = datetime.now(ZoneInfo("Europe/Lisbon")).strftime("%Y%m%d-%H%M%S")
        runs_root = _repo_root() / "output" / "runs"
        run_dir = runs_root / stamp
        if run_dir.exists():
            stamp = f"{stamp}-{os.getpid()}"
            run_dir = runs_root / stamp
        run_dir.mkdir(parents=True, exist_ok=True)
        active_file.write_text(stamp + "\n", encoding="utf-8")
        return stamp, run_dir

    stamp = active_file.read_text(encoding="utf-8").strip()
    run_dir = _repo_root() / "output" / "runs" / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return stamp, run_dir


def _parse_operations(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.operations_file:
        raw = Path(args.operations_file).read_text(encoding="utf-8")
        ops = json.loads(raw)
    elif args.operations:
        ops = json.loads(args.operations)
    elif args.intent:
        entities = json.loads(args.entities)
        if not isinstance(entities, dict):
            raise ValueError("--entities must be a JSON object")
        ops = [{"intent": args.intent, "entities": entities}]
    else:
        raise ValueError("Provide either --intent (with --entities) or --operations / --operations-file")

    if not isinstance(ops, list) or len(ops) == 0:
        raise ValueError("operations must be a non-empty JSON array")

    normalized: list[dict[str, Any]] = []
    for idx, op in enumerate(ops):
        if not isinstance(op, dict):
            raise ValueError(f"operation[{idx}] must be a JSON object")
        intent = op.get("intent")
        if intent not in VALID_INTENTS:
            raise ValueError(f"operation[{idx}].intent '{intent}' is not valid")
        entities = op.get("entities") if op.get("entities") is not None else {}
        if not isinstance(entities, dict):
            raise ValueError(f"operation[{idx}].entities must be a JSON object")
        normalized.append(
            {
                "intent": intent,
                "pipeline": INTENT_TO_PIPELINE[intent],
                "entities": entities,
            }
        )
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Write Stage 01 classified intent(s) and conditional pipeline(s).")
    parser.add_argument("--start", action="store_true", help="Start a new run")
    parser.add_argument("--out-dir", default=None, help="Explicit run output directory")
    parser.add_argument("--raw-text", required=True, help="Verbatim input text")
    parser.add_argument("--actor", required=True, choices=sorted(VALID_ACTORS))
    parser.add_argument("--intent", choices=sorted(VALID_INTENTS), default=None)
    parser.add_argument("--entities", default="{}", help="JSON object of extracted entities (single intent)")
    parser.add_argument("--operations", default=None, help="JSON array of {intent, entities} for multi-call requests")
    parser.add_argument("--operations-file", default=None, help="Path to JSON file containing operations array")
    args = parser.parse_args()

    if not args.raw_text.strip():
        print("ERROR: --raw-text cannot be empty", file=sys.stderr)
        return 1

    try:
        operations = _parse_operations(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    is_action = any(op["intent"] != "non_actionable" for op in operations)
    if is_action and len(operations) > 1:
        operations = [op for op in operations if op["intent"] != "non_actionable"]

    active_pipelines = list(dict.fromkeys(op["pipeline"] for op in operations if op["pipeline"] != "gate"))
    primary = operations[0]
    run_id, run_dir = _resolve_run_dir(args.out_dir, args.start)
    payload = {
        "run_id": run_id,
        "raw_text": args.raw_text,
        "is_olaclick_action": is_action,
        "actor": args.actor,
        "intent": primary["intent"],
        "pipeline": primary["pipeline"],
        "active_pipelines": active_pipelines,
        "entities": primary["entities"],
        "operations": operations,
    }

    out_path = run_dir / "stage01_intent.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
