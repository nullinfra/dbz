# 02 Resolve and execute — Delivery logistics

Resolve and execute the validated operations assigned to `logistics_delivery`.

## Inputs

- Working input is the checked `stage01_intent.json` from [Stage 01](../01_extract/CONTEXT.md). It lives at `<message_dir>/ola_click/<run>/stage01_intent.json`.
- The caller supplies the exact run directory and, for a batch, the assigned operations and runner.
- [Resolution policy](references/policy.md) describes lookups, checks, and outcomes.
- The [shared Stage 02 runner](../../../_shared/tools/rules.md#write-the-orientation) checks the intents and writes the orientation.

## Process

1. Confirm the input contains the assigned `logistics_delivery` operations. Use the policy for delivery quotes, order state, rider assignment, and location checks.
2. Use the shared runner after checking the assigned operations. For a combined run, give the coordinator any policy constraints and invoke the runner once all selected stages have checked their operations.

## Outputs

- `<message_dir>/ola_click/<run>/orientation.json`. For a batch, the runner returns the shared orientation and this stage uses the entries for its assigned operations.

## Check

Check the finalizer's exit status and verify each assigned operation using the [orientation contract](../../../_shared/tools/rules.md#orientation-contract). Use any coverage and delivery status returned for the request.
