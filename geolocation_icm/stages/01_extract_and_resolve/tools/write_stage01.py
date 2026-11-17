#!/usr/bin/env python3
"""Validate the agent's judgment and write the final orientation."""
import argparse
import json
import re
import unicodedata
from difflib import SequenceMatcher
import sys
from pathlib import Path

from typing import Any

from google_maps import load_store_config

OUTPUT = Path(__file__).resolve().parent.parent / "output"
MAPS = OUTPUT / "maps_raw_output.json"
RESULT = OUTPUT / "orientation.json"
API_ERRORS = {"REQUEST_DENIED", "OVER_QUERY_LIMIT", "INVALID_REQUEST", "UNKNOWN_ERROR"}


def _project_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "formatted_address": raw.get("formatted_address", ""),
        "municipality": raw.get("municipality"),
        "postal_code": raw.get("postal_code"),
        "driving_distance_meters": raw.get("driving_distance_meters"),
        "driving_distance_km": raw.get("driving_distance_km"),
        "driving_eta_seconds": raw.get("driving_eta_seconds"),
        "driving_eta_text": raw.get("driving_eta_text"),
        "place_id": raw.get("place_id"),
    }


def _auto_suggested_message(
    q_exec: str,
    candidates: list[dict[str, Any]],
    clarification_reason: str | None,
) -> str | None:
    if not clarification_reason:
        return None
    if clarification_reason == "MULTIPLE_MATCHES":
        opts = "\n".join(
            f"{i}. {c['formatted_address']} ({c.get('municipality') or 'n/a'}, {c.get('postal_code') or 'n/a'})"
            for i, c in enumerate(candidates, start=1)
        )
        return f"Multiple matches found for '{q_exec}'. Ask customer which address is theirs:\n{opts}"
    if clarification_reason == "ADDRESS_NOT_FOUND":
        return f"Address '{q_exec}' not found. Ask customer to verify street spelling, provide postal code/locality, or send a location pin."
    if clarification_reason == "PARTIAL_MATCH":
        c0 = candidates[0]["formatted_address"]
        return f"Closest match for '{q_exec}' is '{c0}'. Ask customer to confirm or provide full street, door number, and postal code/locality."
    if clarification_reason == "MISSING_PREMISE_NUMBER":
        c0 = candidates[0]["formatted_address"]
        return f"Found '{c0}' without a door/building number. Ask customer for the door number."
    if clarification_reason == "NO_USABLE_ROUTE":
        c0 = candidates[0]["formatted_address"]
        return f"Found '{c0}', but no driving route could be calculated. Ask customer for a nearby accessible street, postal code, or location pin."
    return f"Clarification needed ({clarification_reason}) for '{q_exec}'."


def _street_words(text: str) -> list[str] | None:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    match = re.search(r"\b(?:rua|r\.?|avenida|av\.?|travessa|tv\.?|praceta|pct\.?|alameda|praça|praca)\s+", text)
    if not match:
        return None
    name = re.split(r"[,\d]", text[match.end():], maxsplit=1)[0]
    words = re.findall(r"[a-z]+", name)
    return [w for w in words if w not in {"de", "da", "do", "das", "dos", "n", "no", "corroios", "portugal"}]


def _plausible_street(original: str, candidate: dict[str, Any]) -> bool:
    source = _street_words(original)
    if not source:
        return True
    types = set(candidate.get("types") or [])
    if not types.intersection({"street_address", "route", "premise", "subpremise", "intersection"}):
        return False
    target = _street_words(candidate.get("formatted_address") or "")
    if not target:
        return False
    # Each meaningful input word must resemble a word in the suggested street.
    return all(max(SequenceMatcher(None, word, other).ratio() for other in target) >= 0.6 for word in source)


def build_orientation(maps: dict[str, Any], attempts: list[dict[str, Any]], sub_premise_notes: str, destination_type: str = "address", alternatives: list[str] | None = None) -> dict[str, Any]:
    q_exec = maps["query_executed"]
    threshold_m = load_store_config()["driving_distance_meters"]
    raw_cands = maps.get("candidates") or []
    original_query = attempts[0].get("query", "") if attempts else ""
    # Compare each result with each customer-supplied address, not only the first.
    address_parts = re.split(r"\s+(?:ou(?:\s+ent[aã]o)?|or|o)\s+(?:na\s+|no\s+|en\s+)?(?=(?:rua|r\.|avenida|av\.|travessa|praceta|praça|praca|alameda)\b)", original_query, flags=re.IGNORECASE)
    raw_cands = [c for c in raw_cands if any(_plausible_street(part, c) for part in address_parts)]
    candidates = [_project_candidate(c) for c in raw_cands]

    resolution_attempts = [
        {
            "query": a.get("query", ""),
            "verdict": a.get("verdict", ""),
            "note": a.get("note", ""),
        }
        for a in attempts
        if isinstance(a, dict)
    ]

    selected_verdict = next((a.get("verdict") for a in attempts if a.get("query") == q_exec), None)

    has_multiple = len(candidates) > 1

    if selected_verdict == "rejected":
        raw_cands = []
        candidates = []
        has_multiple = False

    if len(candidates) == 0:
        within_50km: Any = "UNRESOLVED_LOCATION"
        eta = None
        resolution_status = maps.get("maps_status") or "ZERO_RESULTS"
        needs_clarification = True
        clarification_reason = "ADDRESS_NOT_FOUND"
    elif has_multiple:
        all_known_within = all(
            isinstance(c.get("driving_distance_meters"), int) and c["driving_distance_meters"] <= threshold_m
            for c in candidates
        )
        within_50km = True if all_known_within else "AMBIGUOUS_MULTIPLE_MATCHES"
        eta = None
        resolution_status = maps.get("maps_status") or "OK"
        needs_clarification = True
        clarification_reason = "MULTIPLE_MATCHES"
    else:
        raw0 = raw_cands[0]
        cand0 = candidates[0]
        meters = cand0.get("driving_distance_meters")
        if raw0.get("distance_matrix_status") != "OK" or not isinstance(meters, int):
            within_50km = "UNRESOLVED_LOCATION"
            eta = None
            resolution_status = raw0.get("distance_matrix_status") or "NO_USABLE_ROUTE"
            needs_clarification = True
            clarification_reason = "NO_USABLE_ROUTE"
        else:
            within_50km = meters <= threshold_m
            eta = cand0.get("driving_eta_text")
            resolution_status = maps.get("maps_status") or "OK"

            types0 = set(raw0.get("types") or [])
            is_poi = bool(types0 & {"establishment", "point_of_interest", "premise", "subpremise"})
            if selected_verdict in ("rejected", "uncertain") or raw0.get("partial_match") or (raw0.get("has_street_number") and raw0.get("premise_verified") is not True):
                needs_clarification = True
                clarification_reason = "PARTIAL_MATCH"
            elif not raw0.get("has_street_number") and is_poi:
                needs_clarification = True
                clarification_reason = "PARTIAL_MATCH"
            elif not raw0.get("has_street_number") and not is_poi:
                needs_clarification = True
                clarification_reason = "MISSING_PREMISE_NUMBER"
            else:
                needs_clarification = False
                clarification_reason = None

    alternatives = alternatives or []
    if len(alternatives) >= 2:
        needs_clarification = True
        clarification_reason = "MULTIPLE_ADDRESSES"
        within_50km = "UNRESOLVED_LOCATION"
        eta = None
    elif destination_type == "poi" and candidates and clarification_reason not in {"MULTIPLE_MATCHES", "NO_USABLE_ROUTE"}:
        needs_clarification = True
        clarification_reason = "PARTIAL_MATCH"

    suggested_msg = _auto_suggested_message(
        original_query if clarification_reason == "ADDRESS_NOT_FOUND" else q_exec, candidates, clarification_reason
    )

    if clarification_reason == "MULTIPLE_ADDRESSES":
        suggested_msg = "Ask customer which delivery address is theirs: " + " or ".join(alternatives) + "?"

    orientation = {
        "is_address": True,
        "destination_type": destination_type,
        "address_alternatives": alternatives,
        "within_50km": within_50km,
        "has_multiple_matches": has_multiple,
        "eta": eta,
        "resolution_status": resolution_status,
        "query_executed": q_exec,
        "candidates": candidates,
        "needs_clarification": needs_clarification,
        "clarification_reason": clarification_reason,
        "suggested_customer_message": suggested_msg,
        "resolution_attempts": resolution_attempts,
        "sub_premise_notes": sub_premise_notes,
    }

    return orientation


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the final geolocation orientation.")
    parser.add_argument("--start", action="store_true", help="Start a new run and clear previous outputs")
    parser.add_argument("--is-address", choices=["true", "false"])
    parser.add_argument("--sub-premise-notes", default="")
    parser.add_argument("--attempts", default="[]")
    parser.add_argument("--destination-type", choices=["address", "poi"], default="address")
    parser.add_argument("--alternatives", default="[]", help="JSON list of customer-supplied alternative delivery addresses")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if args.start:
        for item in OUTPUT.iterdir():
            if item.is_file() or item.is_symlink():
                item.unlink()
        return 0
    if args.is_address is None:
        parser.error("--is-address is required unless --start is used")
    RESULT.unlink(missing_ok=True)
    try:
        if args.is_address == "false":
            if MAPS.exists():
                raise ValueError("Maps output exists for a non-address input")
            result = {"is_address": False}
        else:
            attempts = json.loads(args.attempts)
            if not isinstance(attempts, list) or not attempts or any(
                not isinstance(a, dict) or not isinstance(a.get("query"), str) or not a["query"].strip()
                or a.get("verdict") not in ("accepted", "uncertain", "rejected") for a in attempts
            ):
                raise ValueError("attempts must contain queries and valid verdicts")
            if len(attempts) > 4 or len({a["query"].strip().casefold() for a in attempts}) != len(attempts):
                raise ValueError("attempts must contain at most four distinct queries")
            maps = json.loads(MAPS.read_text(encoding="utf-8"))
            if maps.get("query_executed") not in [a["query"] for a in attempts]:
                raise ValueError("Maps query does not match any recorded attempt")
            if maps.get("maps_status") in API_ERRORS or maps.get("distance_matrix_status") in API_ERRORS:
                raise ValueError("Google Maps returned an API error")
            alternatives = json.loads(args.alternatives)
            if not isinstance(alternatives, list) or any(not isinstance(a, str) or not a.strip() for a in alternatives) or len(alternatives) == 1:
                raise ValueError("alternatives must be empty or contain at least two addresses")
            result = build_orientation(maps, attempts, args.sub_premise_notes, args.destination_type, alternatives)
        RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Geolocation finalization failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
