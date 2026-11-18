# 01_spawn — one `codex exec` per case, in parallel

Run by: `run_codex.py` (no orchestrating sub-agents; they were slow to start). Each case runs `codex exec` with `gpt-6-luna` at `light` reasoning effort.

## Reads
- `maps/output/evals/<eval_id>/eval.json` (list of cases)
- Each `cases/<dir>/prompt.md`, piped verbatim to Codex on stdin

Never read any `exp_*` fields during `01_spawn`.

## Process
1. Run `python3 maps/geolocation_evals/_factory/tools/run_codex.py <eval_id>` (all cases in parallel; `--jobs`, `--model`, `--effort`, `--timeout` are optional).
2. Each Codex run starts cold at the project root, reads `AGENTS.md`, runs Stage 01, and writes outputs only into `cases/<dir>/output/`. Logs go to `cases/<dir>/codex.log` and `codex_last_message.md`.
3. Failed or timed-out cases are not retried.
4. Then run Stage `02_score` (`python3 maps/geolocation_evals/_factory/tools/score.py <eval_id>`), read `summary.md`, and report the results to the user.
