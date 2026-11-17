# Stage 01 tool and command rules

Run all commands from the workspace root: the directory containing `AGENTS.md` and `stages/` (normally `geolocation_icm/`, or the isolated workspace root in an eval). Do not change into `stages/`. Treat all Python files as black boxes: never read any `.py` file. Do not read `_config/*` source files. Use only `tools/google_maps.py` and `tools/write_stage01.py` via the commands below; do not write output files by hand.

## Start and classify

Store the message verbatim as `raw_text`. Do not run `--start` as a separate turn; chain it with the appropriate command below.

For a non-address, run and stop:

```sh
python3 stages/01_extract_and_resolve/tools/write_stage01.py --start && python3 stages/01_extract_and_resolve/tools/write_stage01.py --is-address false
```

This writes `stages/01_extract_and_resolve/output/orientation.json` with `is_address: false`; do not call Maps.

## Address resolution

After classification and extraction according to the [decision rules](../references/extraction_and_maps_rules.md), run the first attempt:

```sh
python3 stages/01_extract_and_resolve/tools/write_stage01.py --start && python3 stages/01_extract_and_resolve/tools/google_maps.py --query "<exact query>" --locality-stated <true|false> --out stages/01_extract_and_resolve/output/maps_raw_output.json
```

The Maps tool writes the JSON directly and prints the same JSON to stdout. For each retry, omit `--start` and use the same Maps command with the new query. If the fallback is an earlier attempt, rerun that query so the output holds the chosen response. The saved response's `query_executed` must exactly match a recorded attempt query. Never hand-edit or copy this output.

Finalize the chosen attempt:

```sh
python3 stages/01_extract_and_resolve/tools/write_stage01.py --is-address true --sub-premise-notes "<notes>" --destination-type <address|poi> --alternatives '<JSON list>' --attempts '<JSON list>'
```

Pass `--alternatives` as `[]` unless the customer supplied alternative delivery addresses; otherwise pass a JSON list containing each original address, including its number. Search the first address independently, and preserve the others in this list. Pass `--destination-type poi` for a named destination, and `address` for a street address even if a place is mentioned as a landmark.

The finalizer validates the chosen Maps response and judgments, runs deterministic policy evaluation, writes `stages/01_extract_and_resolve/output/orientation.json`, and prints it to stdout. Do not re-read that file afterward. Validation or policy failure returns a nonzero exit code. Continue only when the finalizer exits zero and the output file exists. A top-level API or matrix error, including `REQUEST_DENIED`, returns nonzero; `ZERO_RESULTS` after all attempts is valid.

## Maps behavior

- Google Maps is the only allowed source of candidates, distances, and ETAs.
- Each attempt queries Geocoding and Places Text Search, combines their results, and deduplicates matches by Google place ID. Keep every unique result; Places results are not only a fallback for `ZERO_RESULTS`.
- `query_executed` is the attempt's unaltered query. When `locality_stated=false`, the tool also geocodes `<query>, Corroios, Portugal`; if that returns Corroios results, those and matching Corroios Places results become the candidates and `service_area_bias_applied=true`. Unbiased Geocoding and Places results remain in `other_search_candidates`.
- A door number is `premise_verified` only for a `ROOFTOP` geocode. Address Validation `CONFIRMED` does not override an interpolated result.
- Keep all returned candidates with place IDs, formatted addresses, coordinates, types, partial-match flags, municipalities, postal codes, and route statuses. Never collapse candidates based on proximity.
- Google requests use Portugal region bias. The Maps and policy tools use the configuration in the [extraction and resolution rules](../references/extraction_and_maps_rules.md#store-and-service-area).

The threshold is inclusive and uses measured driving distance, not displayed rounded kilometers. Preserve returned municipality and postal code, retain ambiguous candidates inside and outside the service area, and never infer a missing route.
