"""Small Google Maps API tools with a central dispatcher."""

import concurrent.futures
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _load_dotenv() -> None:
    # Walk up parent directories to find .env from either the main workspace or an eval copy.
    current = os.path.abspath(os.path.dirname(__file__))
    env_path = None
    for _ in range(10):
        candidate = os.path.join(current, ".env")
        if os.path.exists(candidate):
            env_path = candidate
            break
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    if not env_path:
        return

    with open(env_path, encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip('"\''))


def _api_key() -> str:
    _load_dotenv()
    key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not key or key == "your-api-key-here":
        raise RuntimeError("Set GOOGLE_MAPS_API_KEY in .env or the environment")
    return key


def _get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    query = urlencode({**params, "key": _api_key()})
    with urlopen(f"{url}?{query}", timeout=30) as response:
        return json.load(response)


CORROIOS_VIEWPORT_BOUNDS = "38.18,-9.72|39.09,-8.57"


def geocode(address: str) -> dict[str, Any]:
    """Geocode an address and return Google's raw JSON response."""
    if not address or not address.strip():
        raise ValueError("address must not be empty")
    return _get_json(
        "https://maps.googleapis.com/maps/api/geocode/json",
        {
            "address": address,
            "region": "pt",
            "bounds": CORROIOS_VIEWPORT_BOUNDS,
            "components": "country:PT",
        },
    )


def places_search(query: str) -> dict[str, Any]:
    """Search Places for a text query and return Google's raw JSON response."""
    if not query or not query.strip():
        raise ValueError("query must not be empty")
    return _get_json(
        "https://maps.googleapis.com/maps/api/place/textsearch/json",
        {"query": query, "region": "pt"},
    )


def validate_address(address: str, locality: str | None = None) -> dict[str, Any]:
    """Validate an address with Address Validation and return raw JSON."""
    if not address or not address.strip():
        raise ValueError("address must not be empty")

    payload: dict[str, Any] = {
        "address": {
            "addressLines": [address],
            "regionCode": "PT",
        }
    }
    if locality:
        payload["address"]["locality"] = locality
    request = Request(
        "https://addressvalidation.googleapis.com/v1:validateAddress"
        f"?{urlencode({'key': _api_key()})}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def postal_code_from_response(response: dict[str, Any]) -> str | None:
    """Extract a postal code from a Geocoding or Places response."""
    for result in response.get("results", []) + response.get("candidates", []):
        for component in result.get("address_components", []):
            if "postal_code" in component.get("types", []):
                return component.get("long_name")

        address = result.get("formatted_address", "")
        for part in address.split(","):
            if len(part.strip()) == 8 and part.strip()[4] == "-":
                return part.strip()
    return None


def _waypoint(value: str) -> dict[str, Any]:
    """Convert an address or 'place_id:...' string into a Routes API waypoint."""
    if value.startswith("place_id:"):
        return {"waypoint": {"placeId": value.split(":", 1)[1]}}
    return {"waypoint": {"address": value}}


def _format_duration_text(seconds: int) -> str:
    """Format measured seconds into a concise duration string."""
    total_minutes = max(1, round(seconds / 60))
    hours, mins = divmod(total_minutes, 60)
    if hours == 0:
        return "1 min" if mins == 1 else f"{mins} mins"
    hour_label = "1 hour" if hours == 1 else f"{hours} hours"
    if mins == 0:
        return hour_label
    min_label = "1 min" if mins == 1 else f"{mins} mins"
    return f"{hour_label} {min_label}"


def distance_matrix(
    origins: list[str], destinations: list[str], mode: str = "driving"
) -> dict[str, Any]:
    """Return a Distance Matrix-shaped response using the Google Routes API."""
    if not origins or not destinations:
        raise ValueError("origins and destinations must not be empty")
    if any(not value.strip() for value in origins + destinations):
        raise ValueError("origins and destinations must contain non-empty strings")

    travel_mode = "DRIVE" if mode.lower() == "driving" else mode.upper()
    payload = {
        "origins": [_waypoint(o) for o in origins],
        "destinations": [_waypoint(d) for d in destinations],
        "travelMode": travel_mode,
        "routingPreference": "TRAFFIC_AWARE",
        "units": "METRIC",
    }
    request = Request(
        "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": _api_key(),
            "X-Goog-FieldMask": (
                "originIndex,destinationIndex,status,condition,distanceMeters,duration"
            ),
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            entries = json.load(response)
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        return {
            "status": "REQUEST_DENIED" if exc.code in (401, 403) else f"HTTP_{exc.code}",
            "error_message": error_body,
            "rows": [],
        }

    rows_by_origin: list[list[dict[str, Any]]] = [
        [{"status": "MISSING_DISTANCE_MATRIX_ELEMENT"} for _ in destinations]
        for _ in origins
    ]
    for entry in entries:
        oi = entry.get("originIndex", 0)
        di = entry.get("destinationIndex", 0)
        if not (0 <= oi < len(origins) and 0 <= di < len(destinations)):
            continue
        condition = entry.get("condition")
        meters = entry.get("distanceMeters")
        duration_str = entry.get("duration", "")
        seconds = (
            int(duration_str[:-1])
            if isinstance(duration_str, str) and duration_str.endswith("s") and duration_str[:-1].isdigit()
            else None
        )
        if condition == "ROUTE_EXISTS" and meters is not None and seconds is not None:
            rows_by_origin[oi][di] = {
                "status": "OK",
                "distance": {"value": meters},
                "duration_in_traffic": {
                    "value": seconds,
                    "text": _format_duration_text(seconds),
                },
            }
        else:
            rows_by_origin[oi][di] = {
                "status": condition or "ZERO_RESULTS",
            }

    return {
        "status": "OK",
        "rows": [{"elements": row} for row in rows_by_origin],
    }


def _candidate_postal_code(result: dict[str, Any]) -> str | None:
    """Extract a postal code from one geocoding or Places candidate."""
    return postal_code_from_response({"results": [result]})


def _candidate_municipality(result: dict[str, Any]) -> str | None:
    """Extract locality or municipality from address_components when available."""
    components = result.get("address_components", [])
    for target_type in ("locality", "administrative_area_level_2", "postal_town"):
        for component in components:
            if target_type in component.get("types", []):
                return component.get("long_name")
    return None


def _has_street_number(result: dict[str, Any]) -> bool:
    """Return whether the candidate has a premise-level street number."""
    for component in result.get("address_components", []):
        if "street_number" in component.get("types", []):
            return True
    # Geocoding can return street-address granularity without component detail.
    return "street_address" in result.get("types", [])


def _is_rooftop(result: dict[str, Any]) -> bool:
    """Return True when Google located the exact building (not an interpolation)."""
    return result.get("geometry", {}).get("location_type") == "ROOFTOP"


def load_store_config() -> dict[str, Any]:
    rules = Path(__file__).resolve().parent.parent / "references" / "extraction_and_maps_rules.md"
    text = rules.read_text(encoding="utf-8")
    match = re.search(r"## Store and service area\s+.*?```json\s*(.*?)\s*```", text, re.S)
    if not match:
        raise ValueError("Store configuration missing from extraction rules")
    config = json.loads(match.group(1))
    if not all(isinstance(config.get(k), str) and config[k] for k in ("origin_name", "origin_place_id", "locality")) or not isinstance(config.get("driving_distance_meters"), int):
        raise ValueError("Invalid store configuration")
    return config


STORE = load_store_config()
SERVICE_AREA_LOCALITY = STORE["locality"]
PINNED_ORIGIN_NAME = STORE["origin_name"]
PINNED_ORIGIN_PLACE_ID = STORE["origin_place_id"]


def _summarize_validation(validation: dict[str, Any] | None) -> dict[str, Any] | None:
    """Compact the Address Validation response into the signals the model reads.

    No judgment happens here: the flags are Google's own (`hasReplacedComponents`, `spellCorrected`,
    `replaced`, `inferred`, `confirmationLevel`, ...). The model decides what they mean.
    """
    if not validation or "error" in validation:
        return validation
    result = validation.get("result", {})
    verdict = result.get("verdict", {})
    address = result.get("address", {})
    return {
        "verdict": {
            key: verdict.get(key)
            for key in (
                "inputGranularity",
                "validationGranularity",
                "geocodeGranularity",
                "addressComplete",
                "hasUnconfirmedComponents",
                "hasInferredComponents",
                "hasReplacedComponents",
            )
        },
        "formatted_address": address.get("formattedAddress"),
        "missing_component_types": address.get("missingComponentTypes", []),
        "unconfirmed_component_types": address.get("unconfirmedComponentTypes", []),
        "unresolved_tokens": address.get("unresolvedTokens", []),
        "components": [
            {
                "type": component.get("componentType"),
                "text": (component.get("componentName") or {}).get("text"),
                "confirmation_level": component.get("confirmationLevel"),
                "replaced": bool(component.get("replaced")),
                "spell_corrected": bool(component.get("spellCorrected")),
                "inferred": bool(component.get("inferred")),
                "unexpected": bool(component.get("unexpected")),
            }
            for component in address.get("addressComponents", [])
        ],
    }


def _candidate_from(item: dict[str, Any]) -> dict[str, Any]:
    """Facts about one Google result. Nothing is filtered or scored: the model judges relevance."""
    location_type = item.get("geometry", {}).get("location_type")
    has_street_number = _has_street_number(item)
    return {
        "formatted_address": item.get("formatted_address", ""),
        "place_id": item.get("place_id"),
        "geometry": {"location": item.get("geometry", {}).get("location")},
        "types": item.get("types", []),
        "partial_match": bool(item.get("partial_match", False)),
        "location_type": location_type,
        "has_street_number": has_street_number,
        "premise_verified": (
            location_type == "ROOFTOP" if has_street_number and location_type else None
        ),
        "municipality": _candidate_municipality(item),
        "postal_code": _candidate_postal_code(item),
    }


def resolve_and_measure(
    query: str, origin: str = PINNED_ORIGIN_NAME, locality_stated: bool = True
) -> dict[str, Any]:
    """Run ONE resolution attempt: geocode `query`, attach Google's signals, distance and ETA.

    The tool never filters, corrects or scores candidates. Deciding whether a result is what the
    customer meant (typos, junk fallbacks, wrong street) belongs to the model, which may call this
    again with a different query (see Stage 01 resolution loop).
    """
    if not query or not query.strip():
        raise ValueError("query must not be empty")

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        geo_future = pool.submit(geocode, query)
        places_future = pool.submit(places_search, query)
        bias_future = (
            pool.submit(geocode, f"{query}, {SERVICE_AREA_LOCALITY}, Portugal")
            if not locality_stated
            else None
        )
        geocode_response = geo_future.result()
        try:
            places_response = places_future.result()
            places_search_status = places_response.get("status")
        except Exception:
            places_response = None
            places_search_status = "ERROR"
        biased_response = bias_future.result() if bias_future else None

    response = geocode_response
    source = "geocode+places_search" if places_search_status == "OK" else "geocode"
    if geocode_response.get("status") == "ZERO_RESULTS" and places_search_status == "OK":
        response = places_response
        source = "places_search"

    service_area_bias_applied = False
    other_search_candidates: list[dict[str, Any]] = []
    geocode_items = geocode_response.get("results") or geocode_response.get("candidates") or []
    places_items = (
        (places_response.get("results") or places_response.get("candidates") or [])
        if places_response and places_response.get("status") == "OK"
        else []
    )
    raw_candidates = geocode_items + places_items
    if biased_response is not None:
        biased = [
            item
            for item in biased_response.get("results", [])
            if SERVICE_AREA_LOCALITY.lower() in item.get("formatted_address", "").lower()
        ]
        if biased:
            unbiased_items = geocode_items + places_items
            other_search_candidates = [
                {
                    "formatted_address": item.get("formatted_address", ""),
                    "types": item.get("types", []),
                    "partial_match": bool(item.get("partial_match", False)),
                }
                for item in unbiased_items
            ]
            raw_candidates = biased
            if places_response and places_response.get("status") == "OK":
                raw_candidates.extend(
                    item
                    for item in places_response.get("results", [])
                    if SERVICE_AREA_LOCALITY.lower()
                    in item.get("formatted_address", "").lower()
                )
            source = "geocode+places_search" if places_items else "geocode"
            service_area_bias_applied = True

    # Combine both Google endpoints while retaining geocoding's richer rooftop and
    # address-component fields when the same place appears in both responses.
    candidates: list[dict[str, Any]] = []
    candidate_indexes: dict[str, int] = {}
    for item in raw_candidates:
        candidate = _candidate_from(item)
        place_id = candidate.get("place_id")
        if place_id and place_id in candidate_indexes:
            existing = candidates[candidate_indexes[place_id]]
            for key, value in candidate.items():
                if existing.get(key) in (None, "", [], {}):
                    existing[key] = value
            continue
        if place_id:
            candidate_indexes[place_id] = len(candidates)
        candidates.append(candidate)

    # Run Distance Matrix and (only when needed) Address Validation in parallel.
    exact_rooftop = (
        len(candidates) == 1
        and not raw_candidates[0].get("partial_match")
        and _has_street_number(raw_candidates[0])
        and _is_rooftop(raw_candidates[0])
    )
    need_validation = not exact_rooftop

    def _run_matrix() -> dict[str, Any]:
        matrix_origin = PINNED_ORIGIN_PLACE_ID if origin == PINNED_ORIGIN_NAME else origin
        destinations = [
            f"place_id:{candidate['place_id']}" if candidate.get("place_id") else candidate["formatted_address"]
            for candidate in candidates
        ]
        return distance_matrix([matrix_origin], destinations, mode="driving")

    def _run_validation() -> dict[str, Any] | None:
        try:
            return _summarize_validation(
                validate_address(query, locality=None if locality_stated else SERVICE_AREA_LOCALITY)
            )
        except Exception as exc:
            return {"error": str(exc)}

    distance_matrix_top_status = None
    distance_matrix_error_message = None
    validation = None

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        matrix_future = pool.submit(_run_matrix) if candidates else None
        val_future = pool.submit(_run_validation) if need_validation else None

        if matrix_future is not None:
            matrix = matrix_future.result()
            distance_matrix_top_status = matrix.get("status")
            distance_matrix_error_message = matrix.get("error_message")
            rows = matrix.get("rows", [])
            elements = rows[0].get("elements", []) if rows else []
            for index, candidate in enumerate(candidates):
                element = elements[index] if index < len(elements) else {}
                status = element.get(
                    "status",
                    distance_matrix_top_status
                    if distance_matrix_top_status and distance_matrix_top_status != "OK"
                    else "MISSING_DISTANCE_MATRIX_ELEMENT",
                )
                distance = element.get("distance", {}) if status == "OK" else {}
                traffic_duration = element.get("duration_in_traffic", {}) if status == "OK" else {}
                duration = element.get("duration", {}) if status == "OK" else {}
                eta = traffic_duration or duration
                meters = distance.get("value")
                candidate.update(
                    {
                        "distance_matrix_status": status,
                        "driving_distance_meters": meters,
                        "driving_distance_km": round(meters / 1000, 3) if meters is not None else None,
                        "driving_eta_seconds": eta.get("value"),
                        "driving_eta_text": eta.get("text"),
                        "eta_source": "duration_in_traffic" if traffic_duration else "duration",
                    }
                )

        if val_future is not None:
            validation = val_future.result()

    return {
        "query_executed": query,
        "service_area_bias_applied": service_area_bias_applied,
        "origin": origin,
        "source": source,
        "geocoding_status": geocode_response.get("status"),
        "places_search_status": places_search_status,
        "maps_status": response.get("status"),
        "api_error_message": response.get("error_message"),
        "distance_matrix_status": distance_matrix_top_status,
        "distance_matrix_error_message": distance_matrix_error_message,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "other_search_candidates": other_search_candidates,
        "address_validation": validation,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Resolve an extracted address query via Google Maps and write JSON."
    )
    parser.add_argument("--query", required=True, help="Exact location query string")
    parser.add_argument(
        "--locality-stated",
        required=True,
        choices=["true", "false"],
        help="Whether the customer stated a locality, municipality, or postal code",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional file path to write the output JSON directly (e.g. output/maps_raw_output.json)",
    )
    arguments = parser.parse_args()
    try:
        result = resolve_and_measure(
            query=arguments.query,
            locality_stated=(arguments.locality_stated == "true"),
        )
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        out_path = arguments.out
        if not out_path:
            active = Path("/tmp/icm-observability/.active-run")
            run_id = active.read_text(encoding="utf-8").strip() if active.is_file() else "default"
            out_path = f"/tmp/icm_maps_{run_id}.json"
        out_dir = os.path.dirname(os.path.abspath(out_path))
        os.makedirs(out_dir, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as out_file:
            out_file.write(encoded + "\n")
        print(encoded)
    except Exception as exc:
        print(json.dumps({"error": str(exc), "query": arguments.query}, ensure_ascii=False))
        raise SystemExit(1)
