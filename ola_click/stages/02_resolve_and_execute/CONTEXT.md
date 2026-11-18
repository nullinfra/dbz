# 02_resolve_and_execute — stage context

Resolves menu/order context against the OlaClick MCP / Public API, enforces deterministic safety and confirmation policies, and writes the final `orientation.json`.

## Inputs

- Working (this run): `ola_click/output/runs/<run_id>/stage01_intent.json`
- Reference (every run): [execution and policy rules](references/execution_and_policy_rules.md)
- Reference (every run): [tool rules](tools/rules.md)

## Process

1. Read `references/execution_and_policy_rules.md` and `tools/rules.md` together in one batch.
2. Never read any `.py` file; invoke `olaclick_mcp.py` and `write_stage02.py` as black-box commands from the project root (`Restaurante/`).
3. If `is_olaclick_action` is `false`, skip `olaclick_mcp.py` and run `write_stage02.py`.
4. Otherwise, run `olaclick_mcp.py` and `write_stage02.py` **chained with `&&` in a single shell call**, then use the printed `orientation.json` directly (no extra file reads).

## Outputs

- `ola_click/output/runs/<run_id>/orientation.json`

## Check

`write_stage02.py` validates the Stage 01 input, MCP response, and policy rules, writes `orientation.json`, prints it to stdout, and exits `0`.
