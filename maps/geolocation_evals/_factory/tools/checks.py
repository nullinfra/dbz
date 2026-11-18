"""Deterministic checks for geolocation ICM eval runs."""

import json
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

STREET_STOPWORDS = {
    "acesso",
    "alameda",
    "autoestrada",
    "avenida",
    "av",
    "azinhaga",
    "beco",
    "calcada",
    "caminho",
    "estrada",
    "estr",
    "jardim",
    "largo",
    "lg",
    "parque",
    "patio",
    "praceta",
    "pct",
    "praca",
    "rotunda",
    "rua",
    "r",
    "travessa",
    "tv",
    "urbanizacao",
    "viela",
    "do",
    "da",
    "dos",
    "das",
    "de",
    "e",
    "em",
}


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


def _street_tokens(street_truth: str) -> list[str]:
    words = _normalize(street_truth).split()
    distinctive = [w for w in words if w not in STREET_STOPWORDS and len(w) >= 3]
    return distinctive or [w for w in words if w not in STREET_STOPWORDS] or words


def _contains_street(text: str | None, street_truth: str) -> bool:
    if not text:
        return False
    norm_text = f" {_normalize(text)} "
    tokens = _street_tokens(street_truth)
    return all(f" {tok} " in norm_text for tok in tokens)


NUMBER_NOISE = {"n", "no", "num", "numero", "nº"}

CONFIRM_PATTERNS = [
    r"confirm",  # confirmar / confirma / confirm / confirmas
    r"\bé (a|o|esta|essa|este|esse)\b",
    r"\bis (this|that|it)\b",
    r"\bes (la|el|esta|esa|este|ese)\b",
    r"\bcorret[ao]\b",
    r"\bcorrect\b",
    r"\bcorrecta\b",
    r"\bqual\b|\bwhich\b|\bcu[aá]l\b|\bop[çc][aã]o\b|\boption\b|\bopci[oó]n\b",
    r"n[úu]mero|\bnumber\b|\bporta\b|\bdoor\b|\bpuerta\b",  # asking for the missing door number
    r"c[óo]digo postal|postal code|c[óo]digo",  # asking for the postal code
]


def _street_part(text: str) -> str:
    """Return the street-name portion: everything before the first digit or comma."""
    head = re.split(r"[,\d]", text or "", maxsplit=1)[0]
    return head


def _street_name_tokens(text: str) -> set[str]:
    words = _normalize(_street_part(text)).split()
    return {w for w in words if w not in STREET_STOPWORDS and w not in NUMBER_NOISE}


def _street_is_in_text(candidate_address: str, raw_text: str) -> bool:
    """True when every distinctive word of the candidate's street name is spelled in the customer's own text."""
    tokens = _street_name_tokens(candidate_address)
    return bool(tokens) and tokens <= set(_normalize(raw_text).split())


def is_exact_match(maps_json: dict[str, Any] | None, s1_json: dict[str, Any] | None = None) -> bool:
    """True only for a 100% match, judged from the customer's own text and Google's raw signals.

    One specific candidate, ROOFTOP when a number was given, no partial match, no Address Validation
    correction, and the street name already spelled in raw_text (so a typo that Google or a retry
    corrected is never "exact").
    """
    if not isinstance(maps_json, dict) or not isinstance(s1_json, dict):
        return False
    cands = maps_json.get("candidates") or []
    if len(cands) != 1 or not isinstance(cands[0], dict):
        return False
    c = cands[0]
    if c.get("partial_match") is True or c.get("premise_verified") is False:
        return False
    if c.get("location_type") not in (None, "ROOFTOP"):
        return False
    validation = maps_json.get("address_validation") or {}
    if (validation.get("verdict") or {}).get("hasReplacedComponents") is True:
        return False
    for comp in validation.get("components") or []:
        if comp.get("type") == "route" and (comp.get("spell_corrected") or comp.get("replaced")):
            return False
    return _street_is_in_text(c.get("formatted_address") or "", s1_json.get("raw_text") or "")


def _check_confirmation(
    maps_json: dict[str, Any] | None, s2_json: dict[str, Any] | None, s1_json: dict[str, Any] | None = None
) -> tuple[bool, str]:
    """A non-exact match must provide a clarification instruction for the parent."""
    if not isinstance(s2_json, dict):
        return False, "missing orientation.json"
    if is_exact_match(maps_json, s1_json) and s2_json.get("clarification_reason") != "MULTIPLE_ADDRESSES" and s2_json.get("destination_type") != "poi":
        return True, "ok (exact match, no confirmation needed)"

    reason = s2_json.get("clarification_reason")
    cands = s2_json.get("candidates") or []
    if reason == "ADDRESS_NOT_FOUND" and not cands:
        return True, "ok (nothing to confirm: ADDRESS_NOT_FOUND)"

    errs: list[str] = []
    if s2_json.get("needs_clarification") is not True:
        errs.append(
            "non-exact match was auto-accepted (needs_clarification="
            f"{s2_json.get('needs_clarification')!r}); a confirmation message is required"
        )
    msg = s2_json.get("suggested_customer_message") or ""
    if reason not in {"NO_USABLE_ROUTE"} and not any(re.search(p, msg, re.IGNORECASE) for p in CONFIRM_PATTERNS):
        errs.append("message does not ask the customer to confirm")
    norm_msg = f" {_normalize(msg)} "
    named = []
    for c in cands:
        toks = _street_name_tokens(c.get("formatted_address", "")) if isinstance(c, dict) else set()
        if toks and all(f" {t} " in norm_msg for t in toks):
            named.append(c)
    has_named_street = any(
        isinstance(c, dict) and _street_name_tokens(c.get("formatted_address", "")) for c in cands
    )
    if has_named_street and not named:
        errs.append("message does not name the proposed street/address")
    return (len(errs) == 0, "ok" if not errs else "; ".join(errs))


def _load_json(path: Path) -> tuple[Any | None, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, f"invalid JSON: {exc}"


def _check_passed(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing check.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    first_line = lines[0].strip().lower() if lines else ""
    if first_line.startswith("pass"):
        return True, "pass"
    return False, f"check.md starts with {first_line!r}"


def _check_street_rule(
    rule: str,
    street_truth: str,
    s3_json: dict[str, Any] | None,
    google_outcome: str | None = None,
    maps_json: dict[str, Any] | None = None,
    s1_json: dict[str, Any] | None = None,
    scenario: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    if not isinstance(s3_json, dict):
        return False, "missing or invalid orientation.json"
    scenario = scenario or {}

    reason = s3_json.get("clarification_reason")
    needs_clar = s3_json.get("needs_clarification")
    within_50km = s3_json.get("within_50km")
    msg = s3_json.get("suggested_customer_message") or ""
    candidates = s3_json.get("candidates") or []
    any_cand_matches = any(
        _contains_street(c.get("formatted_address", ""), street_truth)
        for c in candidates
        if isinstance(c, dict)
    )
    msg_matches = _contains_street(msg, street_truth)

    # A "deformed" input that only differs cosmetically (accents, case, abbreviation) is a normal input.
    if rule == "deformed" and isinstance(s1_json, dict):
        raw = s1_json.get("raw_text") or ""
        if any(
            _street_is_in_text(c.get("formatted_address", ""), raw)
            for c in candidates
            if isinstance(c, dict)
        ):
            rule = "original"

    if rule == "original":
        # Door numbers vary per case, so the expected outcome comes from what Google actually returned.
        if s3_json.get("is_address") is not True:
            return False, f"is_address={s3_json.get('is_address')!r}"
        if within_50km is not True:
            return False, f"within_50km={within_50km!r}"
        if not any_cand_matches and not msg_matches:
            return False, f"neither candidates nor message contain truth {street_truth!r}"
        if is_exact_match(maps_json, s1_json):
            if needs_clar is False:
                return True, "ok (exact match resolved)"
            return False, f"exact match but needs_clarification={needs_clar!r} reason={reason!r}"
        if needs_clar is True and reason in {
            "PREMISE_NUMBER_UNVERIFIED", "PARTIAL_MATCH", "MULTIPLE_MATCHES", "MISSING_PREMISE_NUMBER"
        }:
            return True, f"ok ({reason}: not a 100% match, asks the customer)"
        return False, f"non-exact match not clarified: needs_clarification={needs_clar!r} reason={reason!r}"

    if rule == "missing_number":
        if needs_clar is not True:
            return False, f"no door number but needs_clarification={needs_clar!r}"
        if reason not in {"MISSING_PREMISE_NUMBER", "PARTIAL_MATCH", "MULTIPLE_MATCHES"}:
            return False, f"unexpected clarification_reason={reason!r}"
        if not (msg_matches or any_cand_matches):
            return False, f"message/candidates do not contain street {street_truth!r}"
        if not re.search(r"n[úu]mero|n\.?º|\bporta\b|\bdoor\b|\bnumber\b|\bpuerta\b", msg, re.IGNORECASE):
            return False, "message does not ask for the door number"
        return True, f"ok ({reason} asks for the door number)"

    if rule == "multiple_matches":
        n_cands = len(candidates)
        if n_cands < 2:
            if needs_clar is True:
                return True, "ok (insufficient candidates; clarification requested)"
            if n_cands == 1 and is_exact_match(maps_json, s1_json):
                return True, "ok (one exact Maps result; scenario label alone does not establish alternatives)"
            return False, f"unconfirmed result accepted; got {n_cands} candidate(s)"
        errs = []
        if needs_clar is not True or reason != "MULTIPLE_MATCHES":
            errs.append(f"expected MULTIPLE_MATCHES, got needs_clarification={needs_clar!r} reason={reason!r}")
        if s3_json.get("has_multiple_matches") is not True:
            errs.append("has_multiple_matches is not true")
        if s3_json.get("eta") is not None:
            errs.append("eta must be null for multiple candidates")
        options = len(re.findall(r"(?:^|\s|<br>)\d+[.)]\s", msg))
        if options < n_cands:
            errs.append(f"message lists {options} numbered options for {n_cands} candidates")
        return (len(errs) == 0, "ok" if not errs else "; ".join(errs))

    if rule == "postal_only":
        postal = scenario.get("postal", "")
        q = (s1_json or {}).get("extracted_query") or ""
        errs = []
        if postal and postal.replace("-", "") not in q.replace("-", "").replace(" ", ""):
            errs.append(f"extracted_query lost the postal code {postal!r}: {q!r}")
        if needs_clar is not True:
            errs.append(f"postal code alone was accepted (needs_clarification={needs_clar!r})")
        elif reason not in {"MISSING_PREMISE_NUMBER", "PARTIAL_MATCH", "MULTIPLE_MATCHES", "ADDRESS_NOT_FOUND"}:
            errs.append(f"unexpected clarification_reason={reason!r}")
        if not re.search(r"n[úu]mero|n\.?º|\bporta\b|\bdoor\b|\bnumber\b|\bpuerta\b", msg, re.IGNORECASE):
            errs.append("message does not ask for the door number")
        return (len(errs) == 0, "ok (asks for the door number)" if not errs else "; ".join(errs))

    if rule == "poi":
        poi = scenario.get("poi", "")
        q = (s1_json or {}).get("extracted_query") or ""
        poi_tokens = [t for t in _normalize(poi).split() if len(t) >= 3 and t not in STREET_STOPWORDS and t != "corroios"]
        errs = []
        if not poi_tokens or not all(f" {t} " in f" {_normalize(q)} " for t in poi_tokens):
            errs.append(f"extracted_query lost the place name {poi!r}: {q!r}")
        if s3_json.get("destination_type") != "poi":
            errs.append("named destination was not recorded as a POI")
        if needs_clar is not True:
            errs.append(f"place found by name was accepted without confirmation (needs_clarification={needs_clar!r})")
        return (len(errs) == 0, "ok (POI kept in query and confirmation requested)" if not errs else "; ".join(errs))

    if rule == "poi_note":
        q = _normalize((s1_json or {}).get("extracted_query") or "")
        notes = _normalize((s1_json or {}).get("sub_premise_notes") or "")
        tokens = scenario.get("landmark_tokens", [])
        leaked = [t for t in tokens if f" {t} " in f" {q} "]
        missing = [t for t in tokens if f" {t} " not in f" {notes} "]
        errs = []
        if leaked:
            errs.append(f"landmark leaked into the Maps query: {leaked}")
        if missing:
            errs.append(f"landmark not kept in sub_premise_notes: {missing}")
        ok_rule, detail_rule = _check_street_rule(
            "original", street_truth, s3_json, google_outcome, maps_json, s1_json, scenario
        )
        if not ok_rule:
            errs.append(f"address handling: {detail_rule}")
        return (len(errs) == 0, "ok (landmark kept as note; address resolved normally)" if not errs else "; ".join(errs))

    if rule == "two_addresses":
        streets = scenario.get("streets", [])
        errs = []
        if reason != "MULTIPLE_ADDRESSES":
            errs.append(f"expected MULTIPLE_ADDRESSES, got {reason!r}")
        if s3_json.get("eta") is not None:
            errs.append("ETA must be null until the customer chooses an address")
        alternatives = s3_json.get("address_alternatives") or []
        missing_options = [st for st in streets if not any(_contains_street(a, st) for a in alternatives if isinstance(a, str))]
        if missing_options:
            errs.append(f"alternatives not preserved: {missing_options}")
        if needs_clar is not True:
            errs.append(f"two addresses silently resolved (needs_clarification={needs_clar!r})")
        # Quoting the original query does not present its addresses as options.
        unquoted_msg = re.sub(r"(['\"]).*?\1", " ", msg)
        blob = unquoted_msg
        absent = [st for st in streets if not _contains_street(blob, st)]
        if absent:
            errs.append(f"not surfaced to the customer: {absent}")
        return (len(errs) == 0, "ok (both addresses surfaced)" if not errs else "; ".join(errs))

    if rule == "deformed":
        if not any_cand_matches:
            return False, f"returned candidates do not contain truth {street_truth!r}"
        if needs_clar is False:
            return False, "typo'd street was auto-accepted: a non-exact match must ask the customer to confirm"
        if reason in {"PARTIAL_MATCH", "MULTIPLE_MATCHES", "MISSING_PREMISE_NUMBER"}:
            if msg_matches:
                return True, f"ok ({reason} with truth street)"
            return False, f"suggested_customer_message does not contain truth {street_truth!r}"
        return False, f"unexpected clarification_reason={reason!r}"

    if rule == "seriously_deformed":
        if needs_clar is not True:
            return False, f"expected needs_clarification=true, got {needs_clar!r}"
        if reason == "ADDRESS_NOT_FOUND":
            return True, "ok (ADDRESS_NOT_FOUND)"
        if reason in {"PARTIAL_MATCH", "MULTIPLE_MATCHES"}:
            if any_cand_matches and msg_matches:
                return True, f"ok ({reason} with truth street)"
            return (
                False,
                f"{reason} returned options without truth street {street_truth!r}",
            )
        return False, f"unexpected clarification_reason={reason!r}"

    return False, f"unknown street rule {rule!r}"


def evaluate_case(case_meta: dict[str, Any], case_dir: Path) -> dict[str, Any]:
    """Run all deterministic checks on one completed case directory."""
    # Old eval snapshots used stage-numbered expectation names.
    case_meta = dict(case_meta)
    if "expected_input" not in case_meta and "exp_stage01" in case_meta:
        case_meta["expected_input"] = case_meta["exp_stage01"]
    if "expected_orientation" not in case_meta and "exp_stage03" in case_meta:
        case_meta["expected_orientation"] = case_meta["exp_stage03"]
    direct_orientation = case_dir / "orientation.json"
    direct_out = case_dir / "output"
    workspace = case_dir / "workspace"
    eval_id = case_dir.parent.parent.name
    tmp_maps = Path(tempfile.gettempdir()) / "icm-evals" / eval_id / case_dir.name / "maps_raw_output.json"
    if direct_orientation.is_file() or (not direct_out.is_dir() and not workspace.is_dir()):
        s1_out = case_dir
        s2_out = case_dir
        legacy_out = case_dir / "_nonexistent_legacy_"
        policy_check = s2_out / "policy_check.md"
        maps_path = tmp_maps if tmp_maps.is_file() else case_dir / "maps_raw_output.json"
    elif direct_out.is_dir():
        s1_out = direct_out
        s2_out = direct_out
        legacy_out = direct_out / "_nonexistent_legacy_"
        policy_check = s2_out / "policy_check.md"
        maps_path = direct_out / "maps_raw_output.json"
    else:
        s1_out = workspace / "stages" / "01_extract_and_resolve" / "output"
        legacy_out = workspace / "stages" / "02_policy_and_orientation" / "output"
        # Historical eval workspaces retain the previous artifact layout.
        s2_out = legacy_out if legacy_out.is_dir() else s1_out
        policy_check = s2_out / ("check.md" if s2_out == legacy_out else "policy_check.md")
        maps_path = s1_out / "maps_raw_output.json"

    s1_json, s1_err = _load_json(s1_out / "extraction.json")
    s1_maps_json, s1_maps_err = _load_json(maps_path)
    s2_json, s2_err = _load_json(s2_out / "orientation.json")
    current_contract = not legacy_out.is_dir()

    # Current ICM writes one orientation artifact containing classification,
    # extraction, attempt trace, and policy result. Historical runs keep their
    # original separate-artifact scoring path below.
    single_result = current_contract and isinstance(s2_json, dict)
    if single_result:
        result = s2_json
        attempts = result.get("resolution_attempts") or []
        s1_json = {
            **result,
            "raw_text": case_meta.get("input"),
            "extracted_query": result.get("query_executed"),
            "queries_tried": [a.get("query") for a in attempts],
            "attempts": attempts,
        }
        s1_err = None
        s2_json = result
        s2_err = None

    checks: dict[str, dict[str, Any]] = {}

    # 1. run.complete
    # Current contract branches on the result's actual classification. This
    # keeps a bad classification as one input.fields failure, not a cascade of
    # missing Maps/policy artifacts that correctly follow the false branch.
    exp_halt = (s2_json.get("is_address") is False if current_contract and isinstance(s2_json, dict)
                else case_meta["expected_input"].get("is_address") is False)
    complete_errors: list[str] = []
    if current_contract:
        if s2_err:
            complete_errors.append(f"orientation.json: {s2_err}")
        elif not exp_halt and s1_maps_err:
            complete_errors.append(f"maps_raw_output.json: {s1_maps_err}")
    elif not single_result and s1_err:
        complete_errors.append(f"stage01 extraction.json: {s1_err}")
    if not current_contract and not single_result:
        s1_ok, s1_msg = _check_passed(s1_out / "check.md")
        if not s1_ok:
            complete_errors.append(f"stage01 {s1_msg}")

    if not current_contract and not exp_halt:
        if s1_maps_err:
            complete_errors.append(f"stage01 maps_raw_output.json: {s1_maps_err}")
        if s2_err:
            complete_errors.append(f"stage02 orientation.json: {s2_err}")
        if not single_result:
            s2_ok, s2_msg = _check_passed(policy_check)
            if not s2_ok:
                complete_errors.append(f"stage02 {s2_msg}")

    checks["run.complete"] = {
        "passed": len(complete_errors) == 0,
        "detail": "ok" if not complete_errors else "; ".join(complete_errors),
    }

    # In the current one-stage ICM, orientation.json is the sole final result.
    # When it is absent, downstream policy and trace checks cannot be evaluated;
    # report the incomplete run once instead of manufacturing seven derivative
    # extraction/policy failures from artifacts this version never writes.
    if current_contract and not isinstance(s2_json, dict):
        leak_hits: list[str] = []
        for fpath in s1_out.iterdir() if s1_out.exists() else []:
            if fpath.is_file() and fpath.suffix in {".json", ".md", ".txt"}:
                body = fpath.read_text(encoding="utf-8", errors="replace")
                for marker in ("golden.json", "exp_stage", "exp_message_must_"):
                    if marker in body:
                        leak_hits.append(f"{fpath.name} contains {marker!r}")
        checks["run.no_eval_leak"] = {"passed": not leak_hits, "detail": "ok" if not leak_hits else "; ".join(leak_hits)}
        return {
            "dir": case_meta["dir"], "case_id": case_meta["case_id"],
            "repeat": case_meta.get("repeat", 1), "kind": case_meta["kind"],
            "split": case_meta["split"], "street_truth": case_meta.get("street_truth"),
            "passed": False, "checks": checks, "input": case_meta["input"],
            "expected": {"expected_input": case_meta.get("expected_input"),
                         "expected_orientation": case_meta.get("expected_orientation"),
                         "exp_street_rule": case_meta.get("exp_street_rule"),
                         "google_outcome": case_meta.get("google_outcome")},
            "actual_input": None, "maps": s1_maps_json, "orientation": None,
        }

    # 2. run.no_eval_leak
    leak_hits: list[str] = []
    for out_dir in {s1_out, s2_out}:
        if not out_dir.exists():
            continue
        for fpath in out_dir.iterdir():
            if fpath.is_file():
                text = fpath.read_text(encoding="utf-8", errors="replace")
                for marker in ("golden.json", "exp_stage", "exp_message_must_"):
                    if marker in text:
                        leak_hits.append(f"{fpath.name} contains {marker!r}")
    checks["run.no_eval_leak"] = {
        "passed": len(leak_hits) == 0,
        "detail": "ok" if not leak_hits else "; ".join(leak_hits),
    }

    # 3. input.fields
    s1_mismatches: list[str] = []
    if not isinstance(s1_json, dict):
        s1_mismatches.append("missing or invalid extraction.json")
    else:
        for k, v in case_meta["expected_input"].items():
            if k == "pipeline_directive":
                continue  # Legacy expected metadata.
            if s1_json.get(k) != v:
                s1_mismatches.append(f"{k}: expected {v!r}, got {s1_json.get(k)!r}")
    checks["input.fields"] = {
        "passed": len(s1_mismatches) == 0,
        "detail": "ok" if not s1_mismatches else "; ".join(s1_mismatches),
    }

    if current_contract and exp_halt and case_meta["expected_input"].get("is_address") is not False:
        # Classification disagrees with the expected input type. The pipeline
        # correctly halted according to its own result; score just that gate.
        all_passed = all(c["passed"] for c in checks.values())
        return {
            "dir": case_meta["dir"], "case_id": case_meta["case_id"],
            "repeat": case_meta.get("repeat", 1), "kind": case_meta["kind"],
            "split": case_meta["split"], "street_truth": case_meta.get("street_truth"),
            "passed": all_passed, "checks": checks, "input": case_meta["input"],
            "expected": {"expected_input": case_meta.get("expected_input"),
                         "expected_orientation": case_meta.get("expected_orientation"),
                         "exp_street_rule": case_meta.get("exp_street_rule"),
                         "google_outcome": case_meta.get("google_outcome")},
            "actual_input": s1_json, "maps": s1_maps_json, "orientation": s2_json,
        }

    # 4. input.trace
    if exp_halt:
        checks["input.trace"] = {
            "passed": s1_maps_json is None,
            "detail": "ok (Maps skipped)" if s1_maps_json is None else "maps_raw_output.json ran despite HALT_NON_ADDRESS",
        }
    else:
        if isinstance(s1_json, dict) and isinstance(s1_maps_json, dict):
            q1 = s1_json.get("extracted_query")
            q2 = s1_maps_json.get("query_executed")
            trace_ok = isinstance(q1, str) and q1 == q2 and (not single_result or q2 in [a.get("query") for a in (s1_json.get("attempts") or [])])
            checks["input.trace"] = {
                "passed": trace_ok,
                "detail": "ok" if trace_ok else f"extracted_query={q1!r} != query_executed={q2!r}",
            }
        else:
            checks["input.trace"] = {
                "passed": False,
                "detail": "missing extraction.json or maps_raw_output.json",
            }

    # Check the attempt trace for duplicates and the four-attempt limit.
    if not exp_halt:
        tried = (s1_json or {}).get("queries_tried") if isinstance(s1_json, dict) else None
        errs_att: list[str] = []
        if not isinstance(tried, list) or not tried:
            errs_att.append("queries_tried missing or empty")
        else:
            if len(tried) > 4:
                errs_att.append(f"{len(tried)} attempts (max 4)")
            if len({str(q).strip().lower() for q in tried}) != len(tried):
                errs_att.append("a query was repeated")
            attempts = s1_json.get("attempts") if isinstance(s1_json, dict) else None
            if not isinstance(attempts, list) or len(attempts) != len(tried):
                errs_att.append("attempts missing or not one per query")
        checks["input.attempts"] = {
            "passed": not errs_att,
            "detail": "ok" if not errs_att else "; ".join(errs_att),
        }

    # 5. stage02 expectations (either street_rule or golden expected_orientation)
    street_rule = case_meta.get("exp_street_rule")
    if street_rule:
        passed_rule, detail_rule = _check_street_rule(
            street_rule,
            case_meta.get("street_truth", ""),
            s2_json,
            case_meta.get("google_outcome"),
            s1_maps_json,
            s1_json,
            case_meta.get("scenario"),
        )
        checks["policy.street_rule"] = {"passed": passed_rule, "detail": detail_rule}
    else:
        exp03 = case_meta.get("expected_orientation")
        if exp03 is None:
            checks["policy.fields"] = {
                "passed": s2_json is None,
                "detail": "ok (policy skipped)" if s2_json is None else "orientation.json written despite expected null",
            }
        else:
            s2_mismatches: list[str] = []
            if not isinstance(s2_json, dict):
                s2_mismatches.append("missing or invalid orientation.json")
            else:
                for k, v in exp03.items():
                    if s2_json.get(k) != v:
                        s2_mismatches.append(f"{k}: expected {v!r}, got {s2_json.get(k)!r}")
            checks["policy.fields"] = {
                "passed": len(s2_mismatches) == 0,
                "detail": "ok" if not s2_mismatches else "; ".join(s2_mismatches),
            }

    # 6. policy.grounded_facts
    if not exp_halt:
        if not isinstance(s2_json, dict) or not isinstance(s1_maps_json, dict):
            checks["policy.grounded_facts"] = {"passed": False, "detail": "missing Stage 01 maps or policy JSON"}
        else:
            ground_errs: list[str] = []
            raw_cands = s1_maps_json.get("candidates") or []
            final_cands = s2_json.get("candidates") or []
            eta = s2_json.get("eta")
            if len(final_cands) == 1 and s2_json.get("within_50km") != "UNRESOLVED_LOCATION":
                selected = final_cands[0]
                matches = [c for c in raw_cands if c.get("place_id") and c.get("place_id") == selected.get("place_id")]
                if not matches:
                    ground_errs.append("final candidate does not match a raw Maps candidate by place_id")
                elif eta != matches[0].get("driving_eta_text"):
                    ground_errs.append(f"eta={eta!r} != selected candidate's measured ETA {matches[0].get('driving_eta_text')!r}")
            elif eta is not None:
                ground_errs.append(f"eta must be null for {len(final_cands)} final candidates or an unresolved location, got {eta!r}")

            if s2_json.get("query_executed") != s1_maps_json.get("query_executed"):
                ground_errs.append("stage02 query_executed != stage01 query_executed")

            checks["policy.grounded_facts"] = {
                "passed": len(ground_errs) == 0,
                "detail": "ok" if not ground_errs else "; ".join(ground_errs),
            }

    # 7. policy.message_regex (when configured)
    must_contain = case_meta.get("exp_message_must_contain") or []
    must_not = case_meta.get("exp_message_must_not") or []
    if must_contain or must_not:
        if not isinstance(s2_json, dict):
            checks["policy.message_regex"] = {"passed": False, "detail": "missing orientation.json"}
        else:
            msg = s2_json.get("suggested_customer_message") or ""
            regex_errs: list[str] = []
            for pat in must_contain:
                if not re.search(pat, msg, re.IGNORECASE):
                    regex_errs.append(f"missing pattern /{pat}/")
            for pat in must_not:
                if re.search(pat, msg, re.IGNORECASE):
                    regex_errs.append(f"matched forbidden pattern /{pat}/")
            checks["policy.message_regex"] = {
                "passed": len(regex_errs) == 0,
                "detail": "ok" if not regex_errs else "; ".join(regex_errs),
            }

    # 8. policy.confirmation: non-100% matches must end with an "is this the address?" confirmation
    if not exp_halt:
        ok_conf, detail_conf = _check_confirmation(s1_maps_json, s2_json, s1_json)
        checks["policy.confirmation"] = {"passed": ok_conf, "detail": detail_conf}

    all_passed = all(c["passed"] for c in checks.values())
    return {
        "dir": case_meta["dir"],
        "case_id": case_meta["case_id"],
        "repeat": case_meta.get("repeat", 1),
        "kind": case_meta["kind"],
        "split": case_meta["split"],
        "street_truth": case_meta.get("street_truth"),
        "passed": all_passed,
        "checks": checks,
        "input": case_meta["input"],
        "expected": {
            "expected_input": case_meta.get("expected_input"),
            "expected_orientation": case_meta.get("expected_orientation"),
            "exp_street_rule": street_rule,
            "google_outcome": case_meta.get("google_outcome"),
        },
        "actual_input": s1_json,
        "maps": s1_maps_json,
        "orientation": s2_json,
    }
