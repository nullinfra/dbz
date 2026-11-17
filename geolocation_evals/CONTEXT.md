# Eval pipeline

```
00_prepare   →   01_spawn        →   02_score
script           codex exec x50      script
clear old        one cold            deterministic checks,
results,         sub-agent per       build summary.md,
generate 50      isolated workspace  summary.json,
blind prompts                        inputs_outputs.md
```

**Always run `00_prepare` (`python3 geolocation_evals/_factory/tools/prepare.py`) at the start of every eval.** It creates a new timestamped run folder (`YYYYMMDD-HHMMSS`) under `geolocation_evals/results/` without deleting past runs, and generates 50 fresh cases (`10` random Corroios streets × `3` variants = 30, plus 20 scenarios sampled evenly across six kinds). Every score is deterministic: no model judges anything.

| Stage | Who | Job |
|---|---|---|
| [00_prepare](stages/00_prepare/CONTEXT.md) | `prepare.py` | Sample 10 random streets × 3 variants + 20 scenarios (`50` cases, or `--mode golden`), create `results/<YYYYMMDD-HHMMSS>/cases/<dir>/workspace/` and blind `prompt.md` |
| [01_spawn](stages/01_spawn/CONTEXT.md) | `run_codex.py` | Run one `codex exec` (gpt-6-luna, medium) per `cases/<dir>/prompt.md` in parallel and wait for all to finish |
| [02_score](stages/02_score/CONTEXT.md) | `score.py` | Run deterministic checks from `checks.py`, write `check.json`, `summary.json`, `summary.md`, `inputs_outputs.md`, `status.json` |

`EVAL` = `geolocation_evals/results/<eval_id>/`.
