# 02 Resolve and execute — Clients

Check and execute the verified client operations for this run.

## Inputs

- [Module tool rules](tools/rules.md) define the command arguments and verification for this workflow.

- `<message_dir>/ola_click/<run>/stage01_intent.json` from [Stage 01](../01_extract/CONTEXT.md).
- The assigned run directory and [resolution policy](references/policy.md).
- The branch's existing OlaClick MCP endpoint and API key.

## Process

1. Use the [resolution policy](references/policy.md) for permissions, paging, and write outcomes.
2. Run the [shared Stage 02 runner](../../../_shared/tools/rules.md#write-the-orientation) from the restaurant root with the same directory.

```sh
node ola_click/_shared/tools/run-stage02.cjs "$ola_out"
```

## Outputs

- `<run>/preflight.json` records local validation.
- `<run>/orientation.json` records each operation and its result.

## Check

Check the runner's exit status and each result against the [orientation contract](../../../_shared/tools/rules.md#orientation-contract). Verify the returned client UUID for a profile read or write before reporting completion.
