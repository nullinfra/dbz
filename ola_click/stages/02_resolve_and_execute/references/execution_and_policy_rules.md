# Execution and policy rules (Official OlaClick MCP)

Stage 02 reads `stage01_intent.json` and runs deterministic MCP resolution (`https://public-api.olaclick.app/mcp`) and policy checks via [tool rules](../tools/rules.md). Intent-to-MCP-tool mapping is handled deterministically by `olaclick_mcp.py`.

## 1. Non-actionable gate

- If `is_olaclick_action` is `false`, skip `olaclick_mcp.py` and run only `write_stage02.py` (`status: "NO_ACTION"`).

## 2. Deterministic safety gates

- **Read operations** (`check_menu_item`, `get_menu_category`, `check_store_hours_or_open`, `check_order_status`, `list_active_orders`, `sales_summary`, `quote_delivery`): execute live when `OLACLICK_API_KEY` is set.
- **Write operations** (`create_order`, `update_order`, `advance_order_status`, `apply_coupon_or_promo`, `assign_rider`, `register_payment`, `set_item_out_of_stock`, `restore_item_in_stock`, `edit_menu`, `manage_customer_address`, `manage_promotions` create/update): blocked unless `OLACLICK_ALLOW_WRITES=1`; otherwise `dry_run` → `NEEDS_CONFIRMATION`.
- **Destructive operations** (`cancel_order`, `manage_promotions` delete): blocked unless both `OLACLICK_ALLOW_WRITES=1` and `OLACLICK_ALLOW_DESTRUCTIVE=1`; otherwise `dry_run` → `NEEDS_CONFIRMATION`.

## 3. Missing-entity policy

- Never invent missing IDs or `service_type`. Missing required fields return `status: "NEEDS_CLARIFICATION"` with `suggested_message`.
