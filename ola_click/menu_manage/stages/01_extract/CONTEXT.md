# 01 Extract — Menu management

Extract the operations assigned to `menu_manage`.

## Inputs

- Working input is the verbatim request, known actor, assigned operations and their request order, and any relevant confirmed details or upstream results. For a separate run, use the run directory assigned under this message’s OlaClick output.
- [Extraction rules](references/extraction.md) define intents and entity fields.
- [Intent writer](../../../_shared/tools/rules.md#write-the-intent) specifies how to persist the intent.

## Process

1. Extract the stock or menu operation and preserve the supplied identifiers or search terms. Send requests outside the documented capability back to the router as gates.
2. For a standalone or separate run, write `stage01_intent.json` and return its exact output directory. For a combined run, return the ordered `{"intent": ..., "entities": {...}}` operations to the coordinator for one write.

## Outputs

- `<message_dir>/ola_click/<run>/stage01_intent.json`, or the ordered operations for a combined run.

## Check

Check the assigned scope, intent, and entities against the extraction rules. For a written artifact, require the writer to exit `0` and verify that its operations belong to `menu_manage`. In a combined run, the coordinator validates the merged artifact against each stage's handoff before execution.
