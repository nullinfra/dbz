# Execution and policy rules (Official OlaClick MCP Server)

Decision and safety rules for Stage 02. Follow [tool rules](../tools/rules.md) for commands.

## 1. Official OlaClick MCP Server mapping

- **MCP Server:** `https://public-api.olaclick.app/mcp` (`olaclick-mcp-public-api`, JSON-RPC `tools/call` with `Authorization: Bearer <OLACLICK_API_KEY>`)

| Intent | MCP Class | Official MCP Tool(s) | Required Scope |
|---|---|---|---|
| `check_menu_item` | `read` | `get_menu` (filtered locally by `product_query`) | `menu:read` |
| `get_menu_category` | `read` | `get_menu` (filtered/summarized locally) | `menu:read` |
| `check_store_hours_or_open` | `read` | `get_store_status` | `menu:read` |
| `check_order_status` | `read` | `get_order` | `orders:read` |
| `list_active_orders` | `read` | `get_orders` | `orders:read` |
| `sales_summary` | `read` | `get_orders_summary` | `orders:read` |
| `quote_delivery` | `read` | `get_delivery_quote` | `orders:read` |
| `create_order` | `write` | `create_order` + `add_order_combos` | `orders:write` |
| `update_order` | `write` | `update_order` | `orders:write` |
| `advance_order_status` | `write` | `update_order_status` | `orders:write` |
| `apply_coupon_or_promo` | `write` | `apply_order_coupon` | `orders:write` |
| `assign_rider` | `write` | `assign_rider` | `orders:write` |
| `register_payment` | `write` | `add_order_payment` | `orders:write` |
| `set_item_out_of_stock` | `write` | `update_product_variant` (`stock: 0`) | `menu:write` |
| `restore_item_in_stock` | `write` | `update_product_variant` (`stock: N`) | `menu:write` |
| `edit_menu` | `write` | `update_product` / `update_product_variant` (or `list_kitchens` + `create_category` + `create_product` for bulk) | `menu:write` |
| `manage_customer_address` | `write` | `create_client` / `update_client` | `customers:write` |
| `manage_promotions` | `write` / `destructive` | `create_promotion` / `update_promotion` / `delete_promotion` | `promotions:write` |
| `cancel_order` | `destructive` | `cancel_order` | `orders:write` |

## 2. Deterministic safety gates

- **Read actions**: always safe to execute immediately when `OLACLICK_API_KEY` is configured.
- **Write actions**: blocked from live mutation unless `OLACLICK_ALLOW_WRITES=1`. When `0` (or no key), `olaclick_mcp.py` runs in `dry_run` mode and `write_stage02.py` outputs `NEEDS_CONFIRMATION` / `PLANNED_DRY_RUN`.
- **Destructive actions (`cancel_order`, `manage_promotions` with `operation: "delete"`)**: blocked from live execution unless both `OLACLICK_ALLOW_WRITES=1` and `OLACLICK_ALLOW_DESTRUCTIVE=1`.

## 3. Missing-entity policy

- Do not invent missing IDs (`order_id`, `product_id`, `promotion_id`) or `service_type`.
- When required entities for an intent are missing, `write_stage02.py` sets `status: "NEEDS_CLARIFICATION"` and generates `suggested_message`.
