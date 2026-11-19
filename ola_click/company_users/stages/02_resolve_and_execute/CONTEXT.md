# 02 Resolve and execute — Company & Users

## Inputs

- `<run>/stage01_intent.json` from [Stage 01](../01_extract/CONTEXT.md).
- The branch's existing OlaClick MCP URL and API key. Private staff and client operations require the known actor to be `owner`. Company information and available payment methods can be read for customers.

## Process

1. Invoke the [shared Stage 02 runner](../../../_shared/tools/rules.md#write-the-orientation). It checks pagination, filters, client details and permissions before calling MCP. Keep these operations in their own run because this module supplies tools outside the legacy command's intent set.
2. Client writes use the existing `OLACLICK_ALLOW_WRITES` gate. When a write errors or times out, verify the client record before attempting it again. A duplicate phone response is a reason to find and verify the existing record.
3. For staff and client lists, check pagination before giving a total or calling the list exhaustive. Advance pages when the request asks for all results. For a rider lookup, require one exact match among active staff with the `rider` role. Return its actual UUID for [delivery logistics](../../../logistics_delivery/CONTEXT.md). Share only the fields needed for the request.

## Outputs and check

- `<run>/preflight.json` records local validation.
- `<run>/orientation.json` records each assigned operation. Completed calls expose the API result under `mcp_result.response`. A client write is completed only when the returned client UUID verifies it. Use [the orientation contract](../../../_shared/tools/rules.md#orientation-contract) for other statuses.
