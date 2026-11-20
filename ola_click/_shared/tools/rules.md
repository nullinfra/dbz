# OlaClick shared tool rules

Run from `Restaurante/` and invoke the tools as documented commands. The [router](../../CONTEXT.md) selects the module and its read set. Keep direct MCP intents in a separate run from legacy intents. Direct MCP intents take native argument names. Legacy intents take the fields in the selected module's extraction rules.

## Write the intent

Use the unified writer for every OlaClick intent. Copy the message verbatim to `--raw-text`, without trimming, paraphrasing or joining prior turns.

```sh
o="$MSG/ola_click/$RUN_NAME" && mkdir -p "$o" && \
node ola_click/_shared/tools/write-intent.cjs --quiet \
  --out-dir "$o" --raw-text "$RAW" --actor "$ACTOR" \
  --intent "$INTENT" --entities "$ENTITIES" && \
node ola_click/_shared/tools/run-stage02.cjs --summary "$o"
```

`ACTOR` is `customer`, `owner` or `unknown`. `ENTITIES` is a JSON object. For several operations using the same executor, replace `--intent` and `--entities` with `--operations` (a JSON array of `{"intent":...,"entities":{...}}`) or `--operations-file <path>`. Run independent batches concurrently with `&` and `wait`. Sequence dependent operations and writes to the same target.

## Write the orientation

Always run `run-stage02.cjs --summary "$o"` after the writer. The writer records `stage01_intent.json`. Stage 02 records `preflight.json` and `orientation.json`, including for blocked and unsupported operations. The writer exits nonzero for invalid arguments, unknown intents or mixed executors. The runner exits nonzero for an API error or an invalid Stage 01 artifact. Read the saved orientation when available.

## Multi-turn chat context

From a supplied message directory, run `node .codex/chat-output.cjs context "$MSG"` to locate prior drafts, offers and orientations.

## Orientation contract

| Status | Meaning |
|---|---|
| `COMPLETED` | Action executed and verified. |
| `NEEDS_CLARIFICATION` | Required information is missing, invalid or ambiguous. |
| `UNSUPPORTED_OPERATION` | A platform or business rule prevents the action. |
| `NEEDS_CONFIRMATION` | A write or destructive action was prepared in dry run. |
| `PLANNED_DRY_RUN` | A read was prepared in dry run without an API key. |
| `NO_ACTION` | No action ran. Check the preflight report when this appears in a blocked batch. |
| `API_ERROR` | The finalizer reports an upstream error and exits nonzero. |

Use `needs_clarification`, `confirmation_required` and `suggested_message` from the result. Verify the returned record and values before reporting a write as successful. After a timeout or partial batch, read the affected records before retrying. On HTTP 429, respect the retry interval.

## Native MCP transport

The module tables use the [official MCP guide](https://developers.olaclick.app/docs/mcp) and the connected server's `tools/list` schemas. A † marks a tool returned by the server that was absent from the guide's catalogue. A dash in an argument column means none. Check the connected schema when it differs from the guide. A native command requires a registered ICM route or an authorised native client. A table entry does not register an ICM intent.

For an authorised native client, connect over HTTPS to `https://public-api.olaclick.app/mcp` with branch OAuth or a scoped Bearer key. Keep credentials outside arguments, output files and chat. The session uses `initialize`, `notifications/initialized` and `tools/list` (follow `nextCursor`). Send `tools/call` with `name` and `arguments`. Put path and body arguments in that same object and preserve field casing. Use the scope in the module table. Handle MCP `isError` even when HTTP is 200. The server has no preview flag. Use the ICM write gates for previews.
