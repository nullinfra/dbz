# 01 Extract — Clients

Extract the client operations assigned to this run.

## Inputs

- The verbatim request, known actor, assigned operation order, and any verified client UUIDs or upstream results.
- The assigned directory under this message's `ola_click/`.
- [Extraction rules](references/extraction.md) define intents and exact entity fields.

## Process

1. Extract the assigned intents. If a profile lookup or update needs a search first, resolve it using the [extraction rules](references/extraction.md#client-search) and pass the verified UUID to the dependent run.
2. Write the intent from the restaurant root using the assigned directory as `ola_out`.

```sh
node ola_click/clients/stages/01_extract/tools/write-intent.cjs \
  --out-dir "$ola_out" --raw-text "Lista os cinco clientes com mais pedidos" \
  --actor owner --intent get_clients \
  --entities '{"sort_by":"total_orders","direction":"desc","per_page":5}'
```

For independent operations, supply `--operations` with a JSON array of `{"intent": "...", "entities": {...}}` entries in place of `--intent` and `--entities`.

## Outputs

- `<message_dir>/ola_click/<run>/stage01_intent.json`.

## Check

Require the writer to exit `0` and verify that the artifact contains the assigned `clients` operations in request order. Give [Stage 02](../02_resolve_and_execute/CONTEXT.md) the same run directory.
