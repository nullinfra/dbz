"""Aggregate metrics for an eval run, computed deterministically from scored cases (no model judge)."""

from collections import Counter, defaultdict
from typing import Any

from checks import _contains_street, is_exact_match

STREET_TIERS = ("original", "deformed", "seriously_deformed")
SCENARIO_TIERS = ("missing_number", "multiple_matches", "postal_only", "poi", "poi_note", "two_addresses")
MAX_ATTEMPTS = 4


def _pct(num: int, den: int) -> float | None:
    return round(100 * num / den, 1) if den else None


def _rate(num: int, den: int) -> dict[str, Any]:
    return {"n": num, "of": den, "pct": _pct(num, den)}


def _rule(r: dict[str, Any]) -> str:
    return (r.get("expected") or {}).get("exp_street_rule") or r.get("kind") or "?"


def _attempts(r: dict[str, Any]) -> list[dict[str, Any]]:
    s1 = r.get("actual_input") or {}
    attempts = s1.get("attempts")
    if isinstance(attempts, list) and attempts:
        return [a for a in attempts if isinstance(a, dict)]
    return [{"query": q} for q in (s1.get("queries_tried") or [])]


def _outcome(r: dict[str, Any]) -> str:
    s1 = r.get("actual_input") or {}
    s3 = r.get("orientation")
    if s1.get("is_address") is False:
        return "HALT"
    if not isinstance(s3, dict):
        return "NO_OUTPUT"
    if s3.get("needs_clarification") is False:
        return "RESOLVED"
    return str(s3.get("clarification_reason") or "CLARIFY_?")


def compute_metrics(scored: list[dict[str, Any]]) -> dict[str, Any]:
    runs = [r for r in scored if (r.get("actual_input") or {}).get("is_address") is not False]

    # ---- Safety: never silently accept a non-100% match, always ask when unsure -------------------
    exact_runs, non_exact_with_cands, silent, coverage_ok, friction = [], [], [], [], []
    for r in runs:
        s3, maps, s1 = r.get("orientation"), r.get("maps"), r.get("actual_input")
        if not isinstance(s3, dict):
            continue
        exact = is_exact_match(maps, s1)
        if exact:
            exact_runs.append(r)
            if s3.get("needs_clarification") is True:
                friction.append(r)
            continue
        if s3.get("clarification_reason") == "ADDRESS_NOT_FOUND" and not (s3.get("candidates") or []):
            continue  # nothing to confirm
        non_exact_with_cands.append(r)
        if s3.get("needs_clarification") is not True:
            silent.append(r)
        if (r["checks"].get("policy.confirmation") or {}).get("passed"):
            coverage_ok.append(r)

    # wrong street offered: street cases where candidates were offered but none is the truth street
    street_runs = [r for r in runs if _rule(r) in STREET_TIERS and r.get("street_truth")]
    wrong_street = []
    for r in street_runs:
        s3 = r.get("orientation") or {}
        cands = s3.get("candidates") or []
        if s3.get("clarification_reason") == "ADDRESS_NOT_FOUND" or not cands:
            continue
        if not any(_contains_street(c.get("formatted_address", ""), r["street_truth"]) for c in cands if isinstance(c, dict)):
            wrong_street.append(r)

    # recovery on typo'd inputs: the true street is offered (or resolved) instead of "not found"
    recovery: dict[str, dict[str, int]] = {}
    for tier in ("deformed", "seriously_deformed"):
        tier_runs = [r for r in street_runs if _rule(r) == tier]
        offered = [
            r for r in tier_runs
            if any(
                _contains_street(c.get("formatted_address", ""), r["street_truth"])
                for c in ((r.get("orientation") or {}).get("candidates") or [])
                if isinstance(c, dict)
            )
        ]
        not_found = [r for r in tier_runs if (r.get("orientation") or {}).get("clarification_reason") == "ADDRESS_NOT_FOUND"]
        recovery[tier] = {"total": len(tier_runs), "true_street_offered": len(offered), "not_found": len(not_found)}

    safety = {
        "silent_accepts": {**_rate(len(silent), len(non_exact_with_cands)), "target": "0", "ok": not silent,
                           "dirs": [r["dir"] for r in silent]},
        "confirmation_coverage": {**_rate(len(coverage_ok), len(non_exact_with_cands)), "target": "100%",
                                  "ok": len(coverage_ok) == len(non_exact_with_cands),
                                  "dirs": [r["dir"] for r in non_exact_with_cands if r not in coverage_ok]},
        "wrong_street_offered": {**_rate(len(wrong_street), len(street_runs)), "target": "0", "ok": not wrong_street,
                                 "dirs": [r["dir"] for r in wrong_street]},
        "needless_clarification_on_exact": {**_rate(len(friction), len(exact_runs)), "target": "0", "ok": not friction,
                                            "dirs": [r["dir"] for r in friction]},
    }

    # ---- Retry loop -------------------------------------------------------------------------------
    counts: Counter = Counter()
    verdicts: Counter = Counter()
    retried, recovered, fell_back, too_many = [], [], [], []
    for r in runs:
        att = _attempts(r)
        counts[len(att)] += 1
        for a in att:
            verdicts[str(a.get("verdict") or "?")] += 1
        if len(att) > MAX_ATTEMPTS:
            too_many.append(r["dir"])
        if len(att) >= 2:
            retried.append(r)
            if any(a.get("verdict") in ("accepted", "uncertain") for a in att[1:]):
                recovered.append(r)
        s3 = r.get("orientation") or {}
        if s3.get("clarification_reason") == "ADDRESS_NOT_FOUND":
            fell_back.append(r)
    total_attempts = sum(k * v for k, v in counts.items())
    retry = {
        "attempts_distribution": {str(k): counts[k] for k in sorted(counts)},
        "avg_attempts": round(total_attempts / len(runs), 2) if runs else None,
        "verdicts": dict(verdicts),
        "cases_that_retried": _rate(len(retried), len(runs)),
        "retries_that_recovered": _rate(len(recovered), len(retried)),
        "fell_back_to_not_found": _rate(len(fell_back), len(runs)),
        "over_attempt_limit": {"n": len(too_many), "target": "0", "ok": not too_many, "dirs": too_many},
    }

    # ---- Per-check pass rates ---------------------------------------------------------------------
    per_check: dict[str, list[bool]] = defaultdict(list)
    failure_reasons: Counter = Counter()
    for r in scored:
        for name, c in r["checks"].items():
            per_check[name].append(bool(c["passed"]))
            if not c["passed"]:
                failure_reasons[(name, str(c["detail"]).split(";")[0][:90])] += 1
    checks = {name: _rate(sum(v), len(v)) for name, v in sorted(per_check.items())}

    # ---- By scenario (expected rule) and by door number ------------------------------------------
    by_rule: dict[str, list[bool]] = defaultdict(list)
    for r in scored:
        by_rule[_rule(r)].append(bool(r["passed"]))
    scenarios = {k: _rate(sum(v), len(v)) for k, v in by_rule.items() if k in STREET_TIERS + SCENARIO_TIERS}

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in scored:
        n = r.get("door_number")
        if isinstance(n, int):
            buckets["1-9" if n < 10 else "10-39" if n < 40 else "40+"].append(r)
    door_numbers = {}
    for b, rs in sorted(buckets.items()):
        orig = [r for r in rs if _rule(r) == "original"]
        verified = [r for r in orig if is_exact_match(r.get("maps"), r.get("actual_input"))]
        door_numbers[b] = {
            "pass": _rate(sum(1 for r in rs if r["passed"]), len(rs)),
            "google_verified_number_on_originals": _rate(len(verified), len(orig)),
        }

    # ---- Outcome matrix: what the pipeline answered for each kind of input ------------------------
    matrix: dict[str, Counter] = defaultdict(Counter)
    for r in scored:
        matrix[_rule(r)][_outcome(r)] += 1

    return {
        "safety": safety,
        "recovery": recovery,
        "retry": retry,
        "checks": checks,
        "scenarios": scenarios,
        "door_numbers": door_numbers,
        "outcome_matrix": {k: dict(v) for k, v in sorted(matrix.items())},
        "top_failures": [
            {"check": c, "reason": d, "count": n} for (c, d), n in failure_reasons.most_common(10)
        ],
    }


def _fmt(rate: dict[str, Any]) -> str:
    return "n/a" if rate["pct"] is None else f"{rate['n']}/{rate['of']} ({rate['pct']}%)"


def _dirs(d: dict[str, Any]) -> str:
    return ", ".join(d.get("dirs", [])[:6]) or "-"


def render_metrics_md(m: dict[str, Any]) -> list[str]:
    s, rt = m["safety"], m["retry"]
    mark = lambda ok: "✅" if ok else "❌"  # noqa: E731
    out = [
        "## Safety (what must never happen)",
        "",
        "| Metric | Result | Target | | Cases |",
        "|---|---|---|---|---|",
        f"| Non-100% match accepted without asking | {_fmt(s['silent_accepts'])} | 0 | {mark(s['silent_accepts']['ok'])} | {_dirs(s['silent_accepts'])} |",
        f"| Non-100% matches that got a valid confirmation | {_fmt(s['confirmation_coverage'])} | 100% | {mark(s['confirmation_coverage']['ok'])} | {_dirs(s['confirmation_coverage'])} |",
        f"| Wrong street offered (truth not among options) | {_fmt(s['wrong_street_offered'])} | 0 | {mark(s['wrong_street_offered']['ok'])} | {_dirs(s['wrong_street_offered'])} |",
        f"| Needless question on a 100% match | {_fmt(s['needless_clarification_on_exact'])} | 0 | {mark(s['needless_clarification_on_exact']['ok'])} | {_dirs(s['needless_clarification_on_exact'])} |",
        "",
        "## Retry loop (search, re-read, try again, then fall back)",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Attempts per case (distribution) | {', '.join(f'{k}×: {v}' for k, v in rt['attempts_distribution'].items()) or '-'} |",
        f"| Average attempts | {rt['avg_attempts']} |",
        f"| Attempt verdicts | {', '.join(f'{k}: {v}' for k, v in sorted(rt['verdicts'].items())) or '-'} |",
        f"| Cases that retried | {_fmt(rt['cases_that_retried'])} |",
        f"| Retries that recovered a match | {_fmt(rt['retries_that_recovered'])} |",
        f"| Fell back to not-found + question | {_fmt(rt['fell_back_to_not_found'])} |",
        f"| Over 4 attempts (target 0) | {mark(rt['over_attempt_limit']['ok'])} {rt['over_attempt_limit']['n']} {_dirs(rt['over_attempt_limit'])} |",
        "",
        "## Typo recovery",
        "",
        "| Input tier | Cases | True street offered | Answered not-found |",
        "|---|---|---|---|",
    ]
    for tier, v in m["recovery"].items():
        out.append(f"| {tier} | {v['total']} | {v['true_street_offered']} | {v['not_found']} |")

    out += ["", "## Pass rate by scenario", "", "| Scenario | Passed |", "|---|---|"]
    for k, v in m["scenarios"].items():
        out.append(f"| {k} | {_fmt(v)} |")

    out += ["", "## Pass rate by check", "", "| Check | Passed |", "|---|---|"]
    for k, v in m["checks"].items():
        out.append(f"| {k} | {_fmt(v)} |")

    if m["door_numbers"]:
        out += ["", "## Door numbers", "",
                "| Door number | Pass rate | Google verified the number (originals) |", "|---|---|---|"]
        for b, v in m["door_numbers"].items():
            out.append(f"| {b} | {_fmt(v['pass'])} | {_fmt(v['google_verified_number_on_originals'])} |")

    outcomes = sorted({o for row in m["outcome_matrix"].values() for o in row})
    out += ["", "## What the pipeline answered (scenario × outcome)", "",
            "| Scenario | " + " | ".join(outcomes) + " |", "|---|" + "---|" * len(outcomes)]
    for k, row in m["outcome_matrix"].items():
        out.append(f"| {k} | " + " | ".join(str(row.get(o, "")) for o in outcomes) + " |")

    if m["top_failures"]:
        out += ["", "## Most common failures", "", "| Check | Reason | Count |", "|---|---|---|"]
        for f in m["top_failures"]:
            out.append(f"| {f['check']} | {f['reason'].replace('|', '/')} | {f['count']} |")
    return out + [""]
