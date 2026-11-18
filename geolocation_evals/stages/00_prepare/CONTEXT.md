# 00_prepare — validate and freeze an eval run

1. Run `python3 geolocation_evals/_factory/tools/prepare.py` (defaults to `--mode streets --streets 10 --scenarios 20`, generating `10 * 3 = 30` street cases plus 20 scenario cases = `50` cases from `_factory/corroios_streets.json`; pass `--mode golden` to run `_factory/golden.json`).
2. Preserves all previous runs under `output/evals/` and creates a new timestamped folder `output/evals/<YYYYMMDD-HHMMSS>/` with `eval.json`, `status.json` (`prepared`), and for each case/repeat:
   - `cases/<dir>/prompt.md` (blind prompt)
   - `cases/<dir>/output/` (empty case output directory; no workspace copy is created).

## Scenarios and door numbers

- Each street gets a random door number (1-160), shared by its three variants; expected outcomes come from what Google returns, not from a number-10 probe.
- On top of the 30 street cases, `--scenarios N` (default 20, `0` disables) adds N total cases sampled as evenly as possible across `missing_number`, `multiple_matches`, `postal_only`, `poi`, `poi_note`, `two_addresses`. They sample only inputs recorded by `python3 geolocation_evals/_factory/tools/verify_scenarios.py` (re-run it to refresh `verified_scenarios.json`).
