#!/usr/bin/env python3
"""Probe scenario inputs (ambiguous streets, POIs) with the production resolver and record ground truth.

Writes _factory/verified_scenarios.json. prepare.py only samples scenario inputs recorded here, so every
scenario case has a known Google behaviour (e.g. a street name that really returns >1 candidate).
Cost: about 3-5 Google calls per probed input (same call path as production `resolve_and_measure`).
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
FACTORY = HERE.parent
sys.path.insert(0, str(FACTORY.parent.parent / "geolocation_icm" / "stages" / "01_extract_and_resolve" / "tools"))

from google_maps import resolve_and_measure  # noqa: E402

# Generic street names that exist in several localities around Corroios. Probed WITHOUT a locality.
AMBIGUOUS_STREETS = [
    "Rua da Liberdade",
    "Rua 25 de Abril",
    "Rua Direita",
    "Rua Nova",
    "Rua do Comércio",
    "Rua da Igreja",
    "Rua Primeiro de Maio",
    "Avenida da República",
    "Rua da Escola",
    "Rua dos Pescadores",
    "Travessa da Fonte",
    "Rua do Moinho",
    "Rua da Boavista",
    "Rua Luís de Camões",
    "Avenida dos Bombeiros Voluntários",
]

# Points of interest used as the delivery destination (customer names the place, not a street).
POIS = [
    "Pingo Doce Corroios",
    "Lidl Corroios",
    "Continente Corroios",
    "Fórum Seixal",
    "Estação de Corroios",
    "Câmara Municipal do Seixal",
    "Centro de Saúde de Corroios",
    "Escola Secundária de Corroios",
    "Farmácia Corroios",
    "Piscina Municipal de Corroios",
]


def probe_ambiguous(street: str) -> dict:
    query = f"{street}, 10"
    try:
        res = resolve_and_measure(query, locality_stated=False)
    except Exception as exc:
        return {"input": street, "query": query, "outcome": "error", "detail": str(exc)}
    cands = res.get("candidates", [])
    return {
        "input": street,
        "query": query,
        "outcome": "multiple" if len(cands) > 1 else ("single" if cands else "not_found"),
        "candidate_count": len(cands),
        "service_area_bias_applied": res.get("service_area_bias_applied"),
        "candidates": [c.get("formatted_address") for c in cands],
    }


def probe_poi(poi: str) -> dict:
    try:
        res = resolve_and_measure(poi, locality_stated=True)
    except Exception as exc:
        return {"input": poi, "outcome": "error", "detail": str(exc)}
    cands = res.get("candidates", [])
    return {
        "input": poi,
        "outcome": "found" if cands else "not_found",
        "candidate_count": len(cands),
        "candidates": [c.get("formatted_address") for c in cands],
    }


def main() -> int:
    with ThreadPoolExecutor(max_workers=6) as ex:
        amb = list(ex.map(probe_ambiguous, AMBIGUOUS_STREETS))
        poi = list(ex.map(probe_poi, POIS))
    out = {
        "ambiguous_streets": {r["input"]: r for r in amb},
        "pois": {r["input"]: r for r in poi},
    }
    (FACTORY / "verified_scenarios.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in amb:
        print("AMB", r["outcome"], r.get("candidate_count"), r["input"])
    for r in poi:
        print("POI", r["outcome"], r.get("candidate_count"), r["input"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
