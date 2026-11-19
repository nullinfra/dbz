# 02 Resolve and execute — Order creation

Resolve and execute the validated operations assigned to `order_create`.

## Inputs

- Working input is the checked `stage01_intent.json` from [Stage 01](../01_extract/CONTEXT.md). It lives at `<message_dir>/ola_click/<run>/stage01_intent.json`.
- The caller supplies the exact run directory and, for a batch, the assigned operations and runner.
- [Resolution policy](references/policy.md) describes lookups, checks, and outcomes.
- [Draft readiness](../01_extract/references/draft.md#check-readiness) gates execution.
- [MCP runner and finalizer](../../../_shared/tools/rules.md#write-the-orientation) specify the commands for this stage.

## Process

1. Confirm the input contains the assigned `order_create` operations. Run the draft check for every order after expanding item references and before any customer reply or live order attempt. Keep the report beside the intent.

   ```sh
   node ola_click/order_create/stages/02_resolve_and_execute/tools/check-draft.cjs \
     "$ola_out" > "$ola_out/draft_readiness.json"
   ```

2. A `DRAFT` report identifies missing product identities, choices, or service details. Use current catalogue reads to resolve the affected lines. Preserve the review questions for the [next draft reply](../01_extract/references/draft.md#resolve-choices). Use a separate [preview run](../../../_shared/tools/rules.md#preview-an-order) when the reviewed order needs an amount or live validation before checkout.
3. Live execution requires a zero exit from the draft check and resolution of all known blockers, including checks from any lookup or preview. Use the [order execution command](../../../_shared/tools/rules.md#execute-an-order). For a combined run, give the coordinator the assigned results and blockers and run the batch only when designated and all selected stages have checked their operations.

## Outputs

- `<message_dir>/ola_click/<run>/draft_readiness.json` and `orientation.json`. For a batch, the runner returns the shared orientation and this stage uses the entries for its assigned operations.

## Check

Check the finalizer's exit status and verify each assigned operation using the [orientation contract](../../../_shared/tools/rules.md#orientation-contract). Use any item or service clarification returned for the new order.
