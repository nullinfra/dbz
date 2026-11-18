# Eval configuration

| Setting | Value |
|---|---|
| Execution model | `run_codex.py` runs one cold Codex CLI process per case in parallel |
| Case prompt | `cases/<dir>/prompt.md` — verbatim, nothing added; never mentions expected fields |
| Case output | `maps/output/evals/<eval_id>/cases/<dir>/output/` — no workspace copy is created; all runs share the root `AGENTS.md` and `maps/geolocation_icm/` instructions, config, tools, and references. Message is supplied as the caller query, as required by `AGENTS.md`. |
| Retries | None; a case that errors or stops early fails `run.complete` |
| Artifacts | Current ICM writes `cases/<dir>/output/orientation.json` directly; address cases also write `maps_raw_output.json`. There is no extraction artifact, second policy stage, or `check.md`. |
| Judge | None; every check is deterministic and must follow the current Stage 01 contract |
