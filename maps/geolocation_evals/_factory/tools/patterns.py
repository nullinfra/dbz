"""Failure-pattern report: where do failures cluster? Deterministic, computed from scored cases only."""

import re
import unicodedata
from collections import Counter, defaultdict
from typing import Any

MIN_N = 3  # a feature value needs at least this many runs before it is flagged
LIFT_PTS = 20  # ...and a failure rate at least this many points above the overall rate

STAGE1_CHECKS = {"input.fields", "input.trace", "input.attempts"}
STAGE2_CHECKS = {"policy.street_rule", "policy.fields", "policy.grounded_facts", "policy.message_regex", "policy.confirmation"}

PT_WORDS = {"obrigado", "pode", "morada", "rua", "não", "nao", "encontrámos", "encontramos", "número", "confirmar", "código", "postal", "porta", "é", "esta", "conseguimos"}
EN_WORDS = {"the", "could", "address", "please", "found", "you", "number", "street", "send", "this", "couldn't", "check", "postal"}
ES_WORDS = {"gracias", "dirección", "direccion", "calle", "puede", "número", "hemos", "encontramos", "confirmar", "recibida", "es", "esta", "esta?"}


def _norm(text: str) -> str:
    d = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in d if not unicodedata.combining(ch))


def _lang(text: str) -> str:
    words = set(re.findall(r"[a-záàâãéêíóôõúçñ']+", text.lower()))
    scores = {"pt": len(words & PT_WORDS), "en": len(words & EN_WORDS), "es": len(words & ES_WORDS)}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "?"


def _input_lang(text: str) -> str:
    t = text.lower()
    if re.search(r"\b(hi|pls|deliver|floor)\b", t):
        return "en"
    if re.search(r"\b(hola|entrega en|por favor)\b", t):
        return "es"
    return "pt"


def _rule(r: dict[str, Any]) -> str:
    return (r.get("expected") or {}).get("exp_street_rule") or r.get("kind") or "?"


def features(r: dict[str, Any]) -> dict[str, str]:
    inp = r.get("input") or ""
    truth = r.get("street_truth") or ""
    low = _norm(inp)
    f: dict[str, str] = {"scenario": _rule(r)}
    f["input language"] = _input_lang(inp)
    msg = ((r.get("orientation") or {}).get("suggested_customer_message")) or ""
    if msg:
        f["reply language matches input"] = "yes" if _lang(msg) in (f["input language"], "?") else "NO"
    n = r.get("door_number")
    if isinstance(n, int):
        f["door number"] = "1-9" if n < 10 else "10-39" if n < 40 else "40+"
    if _rule(r) in ("original", "deformed", "seriously_deformed", "missing_number", "poi_note") and truth:
        words = truth.split()
        f["street type"] = words[0] if words else "?"
        f["street name length"] = "1-2 words" if len(words) <= 2 else "3-4 words" if len(words) <= 4 else "5+ words"
        f["street has digit/numeral"] = "yes" if re.search(r"\d|\b[IVXL]{2,}\b", truth) else "no"
        f["street has accents"] = "yes" if _norm(truth) != truth.lower() else "no"
        f["Google outcome for street (n°10 probe)"] = (r.get("expected") or {}).get("google_outcome") or "?"
    f["locality stated"] = "yes" if "corroios" in low else "no"
    f["street type abbreviated"] = "yes" if re.search(r"(^|\s)(r|av|tv|pct|pc|al|lg|estr)\.?\s", low) else "no"
    f["customer wrote in lowercase"] = "yes" if inp == inp.lower() else "no"
    f["contains profanity/noise"] = "yes" if re.search(r"caralho|fds|!!", low) else "no"
    f["landmark/floor note in message"] = "yes" if re.search(r"andar|esq|dto|floor|piso|bloco|portao|campainha|cafe|farmacia", low) else "no"
    att = (r.get("actual_input") or {}).get("queries_tried") or []
    f["attempts used"] = str(len(att)) if att else "0"
    maps = r.get("maps") or {}
    f["raw Maps candidates"] = str(min(len(maps.get("candidates") or []), 3)) + ("+" if len(maps.get("candidates") or []) >= 3 else "")
    return f


def _failed_stage(r: dict[str, Any]) -> str:
    failed = {n for n, c in r["checks"].items() if not c["passed"]}
    if "run.complete" in failed:
        return "run did not complete"
    s1, s2 = failed & STAGE1_CHECKS, failed & STAGE2_CHECKS
    if s1 and s2:
        return "Stage 01 and deterministic policy"
    if s1:
        return "Stage 01 (extract / retry loop)"
    if s2:
        return "Deterministic policy / message"
    return "other"


def _signature(r: dict[str, Any]) -> str:
    names = sorted(n for n, c in r["checks"].items() if not c["passed"])
    return " + ".join(names)


def _short(text: Any, n: int = 160) -> str:
    t = str(text or "").replace("\n", " ").replace("|", "/")
    return t if len(t) <= n else t[: n - 1] + "…"


def render_patterns_md(scored: list[dict[str, Any]], eval_id: str) -> str:
    total = len(scored)
    failed = [r for r in scored if not r["passed"]]
    overall = 100 * len(failed) / total if total else 0.0
    out = [f"# Failure patterns — {eval_id}", ""]
    if not failed:
        out += [f"All {total} runs passed, so there are no failure patterns to report.", ""]
        return "\n".join(out)

    out += [
        f"{len(failed)} of {total} runs failed ({overall:.1f}%). Everything below is computed from the case results, "
        "with no model judge. Small groups are noisy: a pattern is only flagged with "
        f"≥{MIN_N} runs and a failure rate ≥{LIFT_PTS} points above overall. Use `--streets`/`--repeat` to firm one up.",
        "",
    ]

    # ---- 1. which stage broke -----------------------------------------------------------------
    stage = Counter(_failed_stage(r) for r in failed)
    out += ["## 1. Where in the pipeline it broke", "", "| Stage | Failed runs |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in stage.most_common()]

    # ---- 2. recurring failure signatures ---------------------------------------------------------
    sigs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in failed:
        sigs[_signature(r)].append(r)
    out += ["", "## 2. Recurring failure signatures (checks that fail together)", "",
            "| Failing checks | Runs | Scenarios | Example |", "|---|---|---|---|"]
    for sig, rs in sorted(sigs.items(), key=lambda kv: -len(kv[1])):
        kinds = ", ".join(sorted({_rule(r) for r in rs}))
        out.append(f"| {sig} | {len(rs)} | {kinds} | {rs[0]['dir']} |")

    # ---- 3. features with elevated failure rates ----------------------------------------------------
    by_feat: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for r in scored:
        for k, v in features(r).items():
            by_feat[k][v].append(not r["passed"])
    flagged: list[tuple[float, str, str, int, int]] = []
    rows: dict[str, list[tuple[str, int, int]]] = {}
    for feat, vals in by_feat.items():
        if len(vals) < 2:
            continue
        rows[feat] = [(v, sum(x), len(x)) for v, x in sorted(vals.items())]
        for v, x in vals.items():
            rate = 100 * sum(x) / len(x)
            if len(x) >= MIN_N and sum(x) >= 2 and rate >= overall + LIFT_PTS:
                flagged.append((rate - overall, feat, v, sum(x), len(x)))
    out += ["", "## 3. Where failures concentrate", ""]
    if flagged:
        out += ["Flagged (failure rate well above overall):", "",
                "| Feature | Value | Failed / runs | Failure rate | vs overall |", "|---|---|---|---|---|"]
        for lift, feat, v, nf, n in sorted(flagged, reverse=True):
            out.append(f"| {feat} | **{v}** | {nf}/{n} | {100 * nf / n:.0f}% | +{lift:.0f} pts |")
    else:
        out.append("No feature value stands out: failures are spread evenly (or the sample is too small to tell).")
    out += ["", "<details><summary>Failure rate for every feature value</summary>", "",
            "| Feature | Value | Failed / runs | Failure rate |", "|---|---|---|---|"]
    for feat, vs in rows.items():
        for v, nf, n in vs:
            out.append(f"| {feat} | {v} | {nf}/{n} | {100 * nf / n:.0f}% |")
    out += ["", "</details>"]

    # ---- 4. streets that fail more than once ----------------------------------------------------------
    per_street: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in failed:
        if r.get("street_truth") and _rule(r) in ("original", "deformed", "seriously_deformed"):
            per_street[r["street_truth"]].append(r)
    repeat = {k: v for k, v in per_street.items() if len(v) >= 2}
    out += ["", "## 4. Streets that fail in more than one variant", ""]
    if repeat:
        out += ["| Street | Failed variants | Failing checks |", "|---|---|---|"]
        for st, rs in sorted(repeat.items(), key=lambda kv: -len(kv[1])):
            out.append(f"| {st} | {', '.join(r['dir'] for r in rs)} | {_short(' / '.join(sorted({_signature(r) for r in rs})), 120)} |")
    else:
        out.append("None observed. This sample cannot rule out a street-specific cause.")

    # ---- 5. failure details ---------------------------------------------------------------------------
    out += ["", "## 5. Every failure, with what happened", "",
            "| Case | Input | Check | Why it failed | Pipeline answered |", "|---|---|---|---|---|"]
    for r in failed:
        s3 = r.get("orientation") or {}
        answer = s3.get("suggested_customer_message") or s3.get("summary_note") or ("Resolved: " + ", ".join(c.get("formatted_address", "") for c in s3.get("candidates", [])) if s3 else "(no orientation)")
        for name, c in r["checks"].items():
            if not c["passed"]:
                out.append(f"| {r['dir']} | {_short(r.get('input'), 90)} | {name} | {_short(c['detail'], 200)} | {_short(answer, 140)} |")
    return "\n".join(out) + "\n"
