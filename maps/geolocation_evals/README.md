# evals — does the agent follow its own rules?

Runs 50 dynamic cases by default (10 random Corroios streets × `original`, `deformed`, `seriously_deformed` = 30, plus 20 scenarios spread across six kinds: missing number, multiple matches, postal-code-only, POI, landmark note, two addresses) through the real `maps/geolocation_icm` pipeline, one cold `codex exec` (gpt-6-luna, medium) per case, and scores every run deterministically with Python scripts (no LLM judge).

| Need | Go to |
|---|---|
| Run an evaluation | Open the project root (`Restaurante/`) and ask the agent: *"Run `geolocation_evals`"* (always starts fresh with `prepare.py`, generating 50 cases by default) |
| Pipeline stages | [CONTEXT.md](CONTEXT.md) |
| Read the latest run | `maps/output/evals/<eval_id>/summary.md` and `inputs_outputs.md` |
| Re-score an existing run | `python3 maps/geolocation_evals/_factory/tools/score.py <eval_id>` |
| Eval settings | [_factory/config.md](_factory/config.md) |
