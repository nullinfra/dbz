# Back-office operations — Resolution policy

Deterministic checks performed by the [shared tools](../../../../_shared/tools/rules.md#write-the-orientation) for `check_order_status`, `list_active_orders`, `sales_summary`, and `manage_customer_address`:

1. **`check_order_status` & `list_active_orders`:**
   - Check pagination before reporting that a list is complete.
   - Default `start_date` and `end_date` to today in `Europe/Lisbon`.
   - `check_order_status` accepts UUID, `public_id` (`PT-...`), or `daily_id` (`1`, `#2`), or searches today's orders by `customer_name`/`customer_phone` (returning `ORDER_NOT_FOUND` or `AMBIGUOUS_ORDER` when appropriate).
2. **`sales_summary`:**
   - If `start_date > end_date`, never swap the dates silently—run `run-stage02.cjs` with the user's dates so preflight blocks with `NEEDS_CLARIFICATION`.
   - Load the [report tools](../tools/reports.md) for the selected sales, dashboard or cashier report, or the [integration tools](../tools/integrations.md) for a webhook or connector request.
3. **`manage_customer_address`:**
   - Checks `get_clients(filter_phone_number=...)` first before `create_client` to avoid duplicate customer records, then calls `create_address` if `delivery_address` is provided.

See the [native address arguments](../tools/rules.md#saved-addresses) for saved addresses.
