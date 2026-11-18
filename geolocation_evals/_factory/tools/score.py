#!/usr/bin/env python3
"""Stage 02 (score): deterministically score all cases in an eval run and write reports."""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from checks import evaluate_case
from metrics import compute_metrics, render_metrics_md
from patterns import render_patterns_md

EVALS_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_ROOT = EVALS_ROOT.parent / "output" / "evals"
TEMP_EVALS_ROOT = Path("/tmp/icm-evals")


def render_case_report(result: dict[str, Any]) -> str:
    """Render per-case deterministic check report as markdown."""
    status = "PASS" if result.get("passed") else "FAIL"
    lines = [
        f"# Case Report — {result.get('dir', result.get('case_id', 'unknown'))}",
        "",
        f"- **Result:** {status}",
        f"- **Kind:** {result.get('kind')}",
        f"- **Split:** {result.get('split')}",
        f"- **Input:** {result.get('input')}",
        "",
        "## Checks",
        "",
        "| Check | Passed | Detail |",
        "|---|---|---|",
    ]
    for name, c in result.get("checks", {}).items():
        mark = "PASS" if c.get("passed") else "FAIL"
        detail = str(c.get("detail") or "-").replace("\n", " ").replace("|", "\\|")
        lines.append(f"| {name} | {mark} | {detail} |")
    return "\n".join(lines) + "\n"


def score_eval(eval_id: str) -> dict[str, Any]:
    """Score (or re-score) every case in output/evals/<eval_id>/."""
    eval_dir = RESULTS_ROOT / eval_id
    tmp_eval_dir = TEMP_EVALS_ROOT / eval_id
    tmp_eval_dir.mkdir(parents=True, exist_ok=True)
    eval_meta_path = tmp_eval_dir / "eval.json"
    if not eval_meta_path.is_file():
        eval_meta_path = eval_dir / "eval.json"
    eval_meta = json.loads(eval_meta_path.read_text(encoding="utf-8"))
    cases = eval_meta["cases"]

    scored: list[dict[str, Any]] = []
    for case_meta in cases:
        case_dir = eval_dir / "cases" / case_meta["dir"]
        result = evaluate_case(case_meta, case_dir)
        result["door_number"] = case_meta.get("door_number")
        (case_dir / "check.json").unlink(missing_ok=True)
        (case_dir / "report.md").write_text(
            render_case_report(result), encoding="utf-8"
        )
        scored.append(result)

    total = len(scored)
    passed = sum(1 for r in scored if r["passed"])

    # Group by case_id for pass@K / pass^K when repeat > 1
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in scored:
        by_case[r["case_id"]].append(r)
        by_kind[r["kind"]].append(r)
        by_split[r["split"]].append(r)

    pass_at_k = sum(1 for runs in by_case.values() if any(r["passed"] for r in runs))
    pass_all_k = sum(1 for runs in by_case.values() if all(r["passed"] for r in runs))

    summary = {
        "eval_id": eval_id,
        "scored_at_utc": datetime.now(timezone.utc).isoformat(),
        "repeat": eval_meta.get("repeat", 1),
        "total_runs": total,
        "passed_runs": passed,
        "failed_runs": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "unique_cases": len(by_case),
        "pass_at_k": pass_at_k,
        "pass_all_k": pass_all_k,
        "by_kind": {
            k: {
                "passed": sum(1 for r in runs if r["passed"]),
                "total": len(runs),
            }
            for k, runs in sorted(by_kind.items())
        },
        "by_split": {
            s: {
                "passed": sum(1 for r in runs if r["passed"]),
                "total": len(runs),
            }
            for s, runs in sorted(by_split.items())
        },
        "metrics": compute_metrics(scored),
        "cases": scored,
    }

    (tmp_eval_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (eval_dir / "summary.md").write_text(render_markdown(summary), encoding="utf-8")
    (eval_dir / "report.md").write_text(render_patterns_md(scored, eval_id), encoding="utf-8")
    (eval_dir / "inputs_outputs.md").write_text(
        render_inputs_outputs(summary), encoding="utf-8"
    )
    (tmp_eval_dir / "status.json").write_text(
        json.dumps(
            {
                "eval_id": eval_id,
                "state": "done",
                "passed_runs": passed,
                "total_runs": total,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    for stale_json in ("eval.json", "status.json", "summary.json"):
        (eval_dir / stale_json).unlink(missing_ok=True)
    return summary


def render_inputs_outputs(summary: dict[str, Any]) -> str:
    """Render a clean table with only each case's input and recommended message."""
    lines = [
        "| Case | Input | Expected | Result | Recommended Message |",
        "|---|---|---|---|---|",
    ]
    for r in summary["cases"]:
        inp = (r.get("input") or "").replace("\n", " ").replace("|", "\\|")
        s1 = r.get("actual_input") or {}
        s3 = r.get("orientation") or {}
        if s1.get("is_address") is False:
            out = "(HALT_NON_ADDRESS — no geolocation message)"
        elif isinstance(s3, dict):
            msg = s3.get("suggested_customer_message")
            if msg:
                out = msg
            else:
                out = s3.get("summary_note") or "(no clarification needed)"
        else:
            out = "(missing Stage 03 output)"
        out_clean = str(out).replace("\n", "<br>").replace("|", "\\|")
        truth = r.get("street_truth") or "?"
        rule = (r.get("expected") or {}).get("exp_street_rule")
        expected = {
            "original": (
                f"CLARIFY door number (Google only interpolates it) on '{truth}'"
                if (r.get("expected") or {}).get("google_outcome") == "unverified_number"
                else f"EXACT match on '{truth}' (no clarification); if Google's street differs at all, confirm instead"
            ),
            "deformed": f"CLARIFY (PARTIAL/MULTIPLE) offering '{truth}' + 'is this the address?' confirmation (never auto-accept a non-exact match)",
            "seriously_deformed": f"ADDRESS_NOT_FOUND, or CLARIFY offering '{truth}' + 'is this the address?' confirmation",
            "missing_number": f"ASK for the door number on '{truth}' (never accept as resolved)",
            "multiple_matches": f"MULTIPLE_MATCHES: numbered list of every candidate for '{truth}', no auto-pick",
            "postal_only": f"ASK for door number (postal code {truth})",
            "poi": f"POI '{truth}' kept in the query, found place confirmed with the customer",
            "poi_note": f"address '{truth}' resolved normally; landmark stays in sub_premise_notes, not in the query",
            "two_addresses": f"CLARIFY: both addresses surfaced, none silently picked ('{truth}' + second)",
        }.get(rule, "see expected_orientation")
        result = "PASS" if r.get("passed") else "FAIL"
        lines.append(f"| {r['dir']} | {inp} | {expected} | {result} | {out_clean} |")
    return "\n".join(lines) + "\n"


def render_markdown(summary: dict[str, Any]) -> str:
    """Render human-readable summary.md."""
    lines = [
        f"# Eval Summary — {summary['eval_id']}",
        "",
        f"- **Runs passed:** {summary['passed_runs']} / {summary['total_runs']} ({summary['pass_rate'] * 100:.1f}%)",
        f"- **Unique cases (pass@k / pass^k, k={summary['repeat']}):** {summary['pass_at_k']} / {summary['pass_all_k']} of {summary['unique_cases']}",
        "- **Failure-pattern report:** [report.md](report.md)",
        "",
        *render_metrics_md(summary["metrics"]),
        "## By Kind",
        "",
        "| Kind | Passed | Total |",
        "|---|---|---|",
    ]
    for kind, stats in summary["by_kind"].items():
        lines.append(f"| {kind} | {stats['passed']} | {stats['total']} |")

    lines += [
        "",
        "## By Split",
        "",
        "| Split | Passed | Total |",
        "|---|---|---|",
    ]
    for split, stats in summary["by_split"].items():
        lines.append(f"| {split} | {stats['passed']} | {stats['total']} |")

    lines += [
        "",
        "## Cases",
        "",
        "| Dir | Kind | Split | Result | Failed Checks |",
        "|---|---|---|---|---|",
    ]
    for r in summary["cases"]:
        status = "PASS" if r["passed"] else "FAIL"
        failed = ", ".join(
            f"{name} ({c['detail']})"
            for name, c in r["checks"].items()
            if not c["passed"]
        )
        lines.append(f"| {r['dir']} | {r['kind']} | {r['split']} | {status} | {failed or '-'} |")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a completed eval run.")
    parser.add_argument("eval_id", help="Eval ID under output/evals/")
    args = parser.parse_args()

    try:
        summary = score_eval(args.eval_id)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"Eval {summary['eval_id']}: {summary['passed_runs']}/{summary['total_runs']} passed "
        f"(summary: output/evals/{summary['eval_id']}/summary.md, "
        f"patterns: output/evals/{summary['eval_id']}/report.md)"
    )
    return 0 if summary["failed_runs"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
