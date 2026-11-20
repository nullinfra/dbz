# Delivery logistics — Resolution policy

Deterministic checks performed by the [shared tools](../../../../_shared/tools/rules.md#write-the-orientation) for `quote_delivery`, `assign_rider`, `update_delivery_status`, and `report_rider_position`:

1. **`quote_delivery` (`read`):**
   - Always run `quote_delivery` via `run-stage02.cjs` (calls `get_delivery_pricing` and `get_delivery_quote`)—never answer district/zone delivery fees from memory. For an address-specific quote, pass verified coordinates from Maps or a district identifier from pricing. Confirm the pricing mode and coverage before stating a fee. A zero price with a null area means the address is outside configured coverage.
2. **Order & Service-Type Guards (`assign_rider`, `update_delivery_status`, `report_rider_position`):**
   - Resolves `order_id` (UUID, `PT-...`, `daily_id`, or single active order today).
   - Verifies the live order has `service_type == "DELIVERY"` — non-delivery orders (`TAKEAWAY`/`ONSITE`/`TABLE`) return `UNSUPPORTED_OPERATION` (`NOT_A_DELIVERY_ORDER`).
   - Verifies the order is not `CANCELLED` or `FINALIZED`.
3. **Intent-specific Checks:**
   - `assign_rider`: if `unassign: true`, calls `unassign_rider(id)`. For `provider: "olaclick"`, resolve the UUID and name via a [Company & Users lookup](../../../../company_users/CONTEXT.md) for active riders. Pass the UUID as `rider_id`. The order must have moved past `PENDING`. An external rider uses `provider: "api"`.
   - `update_delivery_status`: validates `delivery_status` against the 12 official OlaClick delivery statuses and calls `update_delivery_status(id, delivery_status)`.
   - `report_rider_position`: verifies `latitude` (`-90..90`) and `longitude` (`-180..180`) are present, and checks the order already has a `rider` assigned (otherwise returns `NEEDS_CLARIFICATION` / `NO_RIDER_ASSIGNED`). Uses `order.rider.name` if `rider_name` was omitted.

The [native delivery and logistics reference](../tools/rules.md) distinguishes ICM names like `order_id`, `rider_id` and `rider_name` from MCP `id`, `user_id` and `name`. An MCP delivery status is separate from the order status.
