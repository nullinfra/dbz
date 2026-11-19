# Eval configuration

| Setting | Value |
|---|---|
| Execution model | `run_codex.py` runs one cold Codex CLI process per case in parallel |
| Case prompt | The preparer and binder produce a blind `prompt.md` with an explicit case output path and the original customer message |
| Case output | `<message_dir>/geolocation_eval/cases/<dir>/`, as assigned in the prompt. All runs share the root `AGENTS.md` and the Maps ICM instructions and tools. |
| Retries | None; a case that errors or stops early fails `run.complete` |
| Artifacts | Each case writes `orientation.json` to its assigned directory. Address cases also write `maps_raw_output.json`. |
| Judge | None; every check is deterministic and must follow the current Stage 01 contract |
