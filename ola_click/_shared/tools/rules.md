# OlaClick tool and command rules

Run these commands from `Restaurante/`. Treat the Python tools as black boxes. Set `ola_out` to this run's assigned subdirectory under the [message output directory](../../../tools/chat-output.md). Pass it to every tool in the run.

## Write the intent

For one operation, supply the verbatim message, the known actor (`customer`, `owner`, or `unknown`), the intent, and a JSON entity object:

```sh
python3 ola_click/_shared/tools/cli/write_stage01.py \
  --start \
  --out-dir "$ola_out" \
  --raw-text "Quero ver as opções do menu" \
  --actor customer \
  --intent get_menu_category \
  --entities '{"include_details":true}'
```

For a batch of independent operations:

```sh
python3 ola_click/_shared/tools/cli/write_stage01.py \
  --start \
  --out-dir "$ola_out" \
  --raw-text "<verbatim text>" \
  --actor customer \
  --operations '[{"intent":"get_menu_category","entities":{"include_details":true}},{"intent":"check_store_hours_or_open","entities":{"check_external_apps":true}}]'
```

Use `--operations-file <path>` for a large operations array, such as a bulk menu import. The writer maps its intents to the ICM automatically. Use the [Company & Users writer](../../company_users/stages/01_extract/CONTEXT.md) for that module.

The writer exits `0` for valid input and writes `stage01_intent.json` and stdout. The intent artifact contains `run_id`, `raw_text`, `actor`, `is_olaclick_action`, `intent`, `pipeline`, `active_pipelines`, `entities`, and `operations` (each with `intent`, `pipeline`, and `entities`).

## Write the orientation

Run this command for checked intents, including batches and gate-only runs.

```sh
node ola_click/_shared/tools/run-stage02.cjs "$ola_out"
```

The command writes `preflight.json` with each operation's issues. A blocked run returns an orientation with clarification or an unsupported reason before any MCP call. An unaffected entry in a blocked batch has status `NO_ACTION` and can proceed in a new run if it is independent. A ready run executes its assigned operations and writes `orientation.json`. The same orientation is printed to stdout. The existing Python tools handle legacy intents and gate-only finalization. Company & Users runs use the new module's MCP adapter.

### Execute an order

Use the same runner for ready orders. It runs the draft check and writes `draft_readiness.json` before attempting checkout. Use preview for unfinished orders. After a partial failure, check the order and items already recorded before retrying. When retrying an individual MCP order creation, use the same idempotency key.

## Preview an order

Use a separate order run for preview. Set both write gates to zero and use the same shared runner. The preflight report lists any incomplete selections. A reviewed draft can continue through live read checks and return the proposed checkout without submitting it.

```sh
OLACLICK_ALLOW_WRITES=0 OLACLICK_ALLOW_DESTRUCTIVE=0 \
  node ola_click/_shared/tools/run-stage02.cjs "$ola_out"
```

## Orientation contract

The finalizer writes and prints `orientation.json`. Use the per-operation entries in `results` for mixed requests. They carry the intent, pipeline, status, clarification or unsupported reason, confirmation flags, proposed action, MCP result, and suggested message where applicable.

| Status | Meaning |
|---|---|
| `COMPLETED` | Action executed and verified. |
| `NEEDS_CLARIFICATION` | Required information is missing, invalid, or ambiguous. |
| `UNSUPPORTED_OPERATION` | A platform or business rule prevents the action. |
| `NEEDS_CONFIRMATION` | A write or destructive action was prepared in dry run. |
| `PLANNED_DRY_RUN` | A read was prepared in dry run without an API key. |
| `NO_ACTION` | The request matched the non-actionable gate. |
| `API_ERROR` | The finalizer reports an upstream error and exits nonzero. |

Use `needs_clarification`, `confirmation_required`, and `suggested_message` when replying. A failed tool call needs its exit status and diagnostic checked before using any result.
