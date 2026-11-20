# Promotions — Extraction rules

Use `manage_promotions` with `operation` set to `list`, `get`, `create`, `update` or `delete`. Use `promotion_id` from the verified result for an existing promotion. When the owner names a promotion code or title (e.g. `BALCAO10`) without a `promotion_id`, **always** run `manage_promotions` with `{"operation":"list"}` first to resolve `promotion_id`—never ask the user for the ID. Resolve a name or code by inspecting the available promotion records, then carry the actual ID.

For creation, record `name`, `code`, `discount_type` (`percentage` or `amount`), `discount_value`, `minimum_order_amount`, `valid_from`, `valid_until`, `usage_limit` (positive integer or null for explicitly unlimited), and `published`. Ask for any terms that materially affect the discount and remain unclear. Use dates or ISO-8601 timestamps representing the intended validity window in Europe/Lisbon.

For updates, supply only the desired changes. Optional restrictions are `promotion_type`, `products`, `service_types`, `audience`, `usage_limit_per_customer`, `schedule`, and `terms`. For a product-specific offer, set `promotion_type: "products"` and pass the exact `products: [{"id":"...","name":"..."}]` selected from the [current catalogue](../../../../references/catalog-resolution.md). Resolve ingredient or category language before expanding the product list.

For listing, use `service_type_filter` when specified. Use `redeemable_now: true` for promotions redeemable at this time. In native MCP, the corresponding arguments are `service_type` for `get_active_promotions`, `coupon_code` for `create_promotion` and `id` for a promotion UUID. See the [promotion command reference](../../02_resolve_and_execute/tools/rules.md#native-promotion-tools) for the full schemas.
