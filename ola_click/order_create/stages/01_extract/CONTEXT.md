# 01 Extract — Order creation

Extract the operations assigned to `order_create`.

## Inputs

- Working input is the verbatim request, known actor, assigned operations and their request order, and any relevant confirmed details or upstream results. For a separate run, use the run directory assigned under this message’s OlaClick output.
- [Extraction rules](references/extraction.md) define intents and entity fields.
- [Draft and checkout rules](references/draft.md) govern multi-turn order changes, ordered offers, and when a draft is ready for Stage 02.
- [Menus, boxes, and other special items](references/menus_and_boxes.md) applies to every matching item in the expanded basket.
- [Intent writer](../../../_shared/tools/rules.md#write-the-intent) specifies how to persist the intent.

## Process

1. Extract one `create_order` operation. Expand catalog or offer references before checking the items. Merge details already confirmed for the draft, and preserve unresolved choices, quantities, and notes in the fields named in the extraction rules.
2. Write `stage01_intent.json` and return its exact run directory and any known blockers to [Stage 02](../02_resolve_and_execute/CONTEXT.md). Stage 02 checks readiness and previews an unfinished draft. For a combined run, give the coordinator checked operations in request order and flag any known blockers.

## Outputs

- `<message_dir>/ola_click/<run>/stage01_intent.json`, or the ordered operations for a combined run.

## Check

Check the assigned scope, intent, and entities against the extraction rules. For a written artifact, require the writer to exit `0` and verify that its operations belong to `order_create`. In a combined run, the coordinator validates the merged artifact against each stage's handoff before execution.
