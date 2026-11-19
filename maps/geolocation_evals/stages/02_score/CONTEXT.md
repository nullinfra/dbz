# 02_score — deterministic scoring and reporting

Run `python3 maps/geolocation_evals/_factory/tools/score.py "$eval_dir"` using the absolute evaluation directory from Stage 00.

The scorer checks each case's artifacts and writes `summary.md`, `inputs_outputs.md`, and reports inside `eval_dir`. Open `<eval_dir>/summary.md` for the results. A failing case can produce a nonzero exit status with a summary.

Can be re-run at any time after updating a checker (`--recheck` behavior is built in).
