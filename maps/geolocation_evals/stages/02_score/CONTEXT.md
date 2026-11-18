# 02_score — deterministic scoring and reporting

Run `python3 maps/geolocation_evals/_factory/tools/score.py <eval_id>`.

Reads each `cases/<dir>/output/`, runs all deterministic checks in `maps/geolocation_evals/_factory/tools/checks.py`, writes `cases/<dir>/check.json`, and builds `summary.json`, `summary.md`, `inputs_outputs.md`, and `status.json` (`done`).

Can be re-run at any time after updating a checker (`--recheck` behavior is built in).
