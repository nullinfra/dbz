# Eval pipeline

```
00_prepare   →   01_spawn        →   02_score
script           codex exec x50      script
clear old        one cold            deterministic checks,
results,         sub-agent per       build summary.md,
generate 50      isolated workspace  summary.json,
blind prompts                        inputs_outputs.md
```

Start each evaluation with [00_prepare](stages/00_prepare/CONTEXT.md). The evaluation lives in `<message_dir>/geolocation_eval/` under the [chat output directory](../../tools/chat-output.md). The default run generates 50 cases from ten Corroios streets and twenty additional scenarios. Every case is scored with deterministic checks.

| Stage | Who | Job |
|---|---|---|
| [00_prepare](stages/00_prepare/CONTEXT.md) | `prepare.py`, case output binder | Sample cases, generate blind prompts, and assign case output directories |
| [01_spawn](stages/01_spawn/CONTEXT.md) | `run_codex.py` | Run one `codex exec` (gpt-6-luna, medium) per `cases/<dir>/prompt.md` in parallel from the root workspace and wait for all to finish |
| [02_score](stages/02_score/CONTEXT.md) | `score.py` | Run deterministic checks and write the summary and case reports |

Pass the same absolute `eval_dir` to all three stages.
