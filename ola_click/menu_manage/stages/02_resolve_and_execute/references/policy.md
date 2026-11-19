# Menu management — Resolution policy

The [shared tools](../../../../_shared/tools/rules.md#write-the-orientation) check `set_item_out_of_stock`, `restore_item_in_stock`, and `edit_menu`. For stock changes covering several products, resolve the exact targets and run a scoped operation for each.

1. **Strict Disambiguation on Writes (`AMBIGUOUS_PRODUCT` / `AMBIGUOUS_VARIANT`):**
   - Use the live product ID for the selected catalogue item.
   - If 0 products match → `NEEDS_CLARIFICATION` (`ITEM_NOT_FOUND`).
   - If **>1 products match without an exact match** (e.g. *"mete a empada out of stock"* matching 4 empadas) → **never** mutates `matches[0]`; returns `NEEDS_CLARIFICATION` (`AMBIGUOUS_PRODUCT`) listing all candidates.
   - If the product has >1 variants and `variant_id` was not specified → returns `NEEDS_CLARIFICATION` (`AMBIGUOUS_VARIANT`).
2. **Stock Tracking Constraint (`set_item_out_of_stock` / `restore_item_in_stock`):**
   - Calls `get_product(id)` to check `stock_enabled`.
   - Calls `update_product_variant(id, variantId, stock=0)` (or `stock=N`).
   - If `stock_enabled` is `false` on the product, OlaClick ignores variant `stock=0` on the storefront and MCP's `update_product` only exposes `name`/`description` (not `stock_enabled` or `visible`). In that case, `write_stage02.py` flags `STOCK_TRACKING_DISABLED_ON_PRODUCT` (`UNSUPPORTED_OPERATION`) explaining that `stock_enabled` must be enabled once in the OlaClick panel (or the whole category can be hidden via `update_category`).
3. **Price & Field Validation (`edit_menu`):**
   - Negative prices (`price < 0`) or negative stock (`stock < 0`) are rejected deterministically (`INVALID_MENU_PATCH`).
   - Category visibility updates (`category_query` + `patch.visible`) resolve the category from `list_categories` and call `update_category`.
   - Bulk `edit_menu` (`categories` list) checks `list_categories` first to reuse existing category UUIDs (avoiding duplicates) and creates products in parallel using the default kitchen from `list_kitchens`.
