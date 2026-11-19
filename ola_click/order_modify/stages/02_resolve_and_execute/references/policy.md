# Order modification — Resolution policy

- Resolve references to the current order and distinguish the exact line for each change. Verify source, status and the active line IDs. The executor validates all reviewed additions before running any part of an item change. It preserves the original variant, modifiers and comment when adjusting an existing line's quantity.
- Swaps and decreases can require a new line and removal of an old one. The shared runner previews the actual changes. The executor adds any replacement before removing its source. A failed multi-step change requires checking which actions succeeded before retrying. Line removal uses the destructive gate.
- Cancellation uses the API reason code and checks existing payments. Coupons require a client on the order. Status changes follow the documented API progression.
- Use a verified ID for each payment method, payment and discount. Resolve payment methods against the list for this order's service. Determine the amount from the request, or the unpaid balance for a single payment when requested. Carry distinct amounts for split payments.
- Use the [OlaClick MCP reference](https://developers.olaclick.app/docs/mcp#orders) for operation scope and applicability.
