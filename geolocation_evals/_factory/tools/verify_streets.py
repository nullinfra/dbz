#!/usr/bin/env python3
"""Probe every candidate street against Google Geocoding and record what Google actually returns.

Writes _factory/verified_streets.json. prepare.py only samples streets Google can find, and uses the
recorded outcome as the expected result for the 'original' variant.
Cost: one Geocoding call per street (query is '<street>, 10, Corroios', same shape as the original case).
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
FACTORY = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(FACTORY.parent.parent / "geolocation_icm" / "stages" / "01_extract_and_resolve" / "tools"))

from checks import _contains_street  # noqa: E402
from google_maps import geocode  # noqa: E402


def probe(street: str) -> dict:
    query = f"{street}, 10, Corroios"
    try:
        resp = geocode(query)
    except Exception as exc:  # network/API error: leave unknown, never treat as not found
        return {"street": street, "query": query, "outcome": "error", "detail": str(exc)}
    status = resp.get("status")
    if status == "ZERO_RESULTS":
        return {"street": street, "query": query, "outcome": "not_found", "status": status}
    if status != "OK":
        return {"street": street, "query": query, "outcome": "error", "detail": status}
    for r in resp.get("results", []):
        addr = r.get("formatted_address", "")
        if _contains_street(addr, street) and ("Corroios" in addr or "2855" in addr):
            loc = r.get("geometry", {}).get("location_type")
            partial = bool(r.get("partial_match"))
            outcome = "exact" if loc == "ROOFTOP" and not partial else "unverified_number"
            return {"street": street, "query": query, "outcome": outcome,
                    "formatted_address": addr, "location_type": loc, "partial_match": partial}
    top = (resp.get("results") or [{}])[0].get("formatted_address")
    return {"street": street, "query": query, "outcome": "not_found", "status": status, "top_result": top}


def main() -> int:
    streets = json.loads((FACTORY / "corroios_streets.json").read_text(encoding="utf-8"))["streets"]
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(probe, streets))
    counts: dict = {}
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    out = {"counts": counts, "streets": {r["street"]: r for r in results}}
    (FACTORY / "verified_streets.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
