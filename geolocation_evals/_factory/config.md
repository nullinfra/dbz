# Eval configuration

| Setting | Value |
|---|---|
| Execution model | `run_codex.py` runs one cold Codex CLI process per case in parallel |
| Case prompt | `cases/<dir>/prompt.md` — verbatim, nothing added; never mentions `golden.json` or expected fields |
| Case workspace | `results/<eval_id>/cases/<dir>/workspace/` — isolated copy of current `geolocation_icm/` instructions, config, tools and references, with empty stage outputs. Message is supplied as the caller query, as required by current `AGENTS.md`. |
| Retries | None; a case that errors or stops early fails `run.complete` |
| Artifacts | Current ICM writes `stages/01_extract_and_resolve/output/orientation.json` directly; address cases also write `maps_raw_output.json`. There is no extraction artifact, second policy stage, or `check.md`. |
| Judge | None; every check is deterministic and must follow the current Stage 01 contract |
