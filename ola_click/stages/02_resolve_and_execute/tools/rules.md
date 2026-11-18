# Stage 02 tool and command rules

Run all commands from the project root (`Restaurante/`). Never read any `.py` file; this document specifies the exact input/output contracts of `olaclick_mcp.py` and `write_stage02.py`.

## 1. Non-actionable input

If `stage01_intent.json` has `is_olaclick_action: false`, skip `olaclick_mcp.py` and run only:

```sh
python3 ola_click/stages/02_resolve_and_execute/tools/write_stage02.py
```

## 2. Actionable input (1 or N operations in ONE chained command)

Both tools automatically read all `operations` from `stage01_intent.json`, execute independent calls in parallel, and write `orientation.json`:

```sh
python3 ola_click/stages/02_resolve_and_execute/tools/olaclick_mcp.py && python3 ola_click/stages/02_resolve_and_execute/tools/write_stage02.py
```

Optional flags on both tools: `--run-id <run_id>` or `--out-dir <path>` (by default both read/write the active run from Stage 01).

## 3. Deterministic execution & output contract

- **Menu sharing:** `GET /v1/menu` runs at most **once** per run and is reused across all operations in the batch.
- **Parallelism:** Independent operations run concurrently in Python; bulk `edit_menu` (`categories` list) creates categories then creates products in parallel.
- **Safety gates:** `read` operations execute live when `OLACLICK_API_KEY` is set; `write` and `destructive` operations stay in `dry_run` unless `OLACLICK_ALLOW_WRITES=1` (and `OLACLICK_ALLOW_DESTRUCTIVE=1` for `destructive`).
- **Output (`orientation.json` + stdout):**
  - Top-level: `run_id`, `status` (`COMPLETED` | `NEEDS_CLARIFICATION` | `NEEDS_CONFIRMATION` | `PLANNED_DRY_RUN` | `NO_ACTION` | `API_ERROR`), `needs_clarification`, `confirmation_required`, `operations_count`, `results: [...]`, `suggested_message`.
  - Each entry in `results`: `intent`, `status`, `needs_clarification`, `confirmation_required`, `proposed_action`, `mcp_result` (`mode`, `http_status`, `menu_matches`, `menu_summary`, `sales_summary`, `response`), `suggested_message`.
  - Exits `0` unless a required input is missing or `status == "API_ERROR"`.
