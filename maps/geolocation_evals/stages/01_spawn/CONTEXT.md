# 01_spawn — one `codex exec` per case, in parallel

Run by: `run_codex.py` (no orchestrating sub-agents; they were slow to start). Each case runs `codex exec` with `gpt-6-luna` at `light` reasoning effort.

## Reads
- `<eval_dir>/eval.json` (list of cases)
- Each prepared and bound `prompt.md`, piped verbatim to Codex on stdin

Never read any `exp_*` fields during `01_spawn`.

## Process
1. Run `RESTAURANTE_EVAL_WORKER=1 python3 maps/geolocation_evals/_factory/tools/run_codex.py "$eval_dir"` (all cases in parallel; `--jobs`, `--model`, `--effort`, `--timeout` are optional).
2. Each Codex run reads `AGENTS.md`, uses the output assignment in its prompt, and writes orientation and Maps response files under `<eval_dir>/cases/<dir>/`. The worker's lifecycle hooks defer to that assignment, and the runner keeps its logs inside the evaluation directory.
3. Failed or timed-out cases are not retried.
4. Then run [02_score](../02_score/CONTEXT.md), read `<eval_dir>/summary.md`, and report the results to the user.
