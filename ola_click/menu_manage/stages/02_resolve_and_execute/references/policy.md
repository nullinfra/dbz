# Menu management — Resolution policy

The [shared tools](../../../../_shared/tools/rules.md) check `set_item_out_of_stock`, `restore_item_in_stock`, `edit_menu`, and `update_product_variant`. For stock changes covering several products, resolve the exact targets and run a scoped operation for each.

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

## Variant edits

1. Send the direct `update_product_variant` intent through `write-intent.cjs` and `run-stage02.cjs`. Its `entities` are the official MCP arguments: `id` is the parent UUID, `variantId` (case-sensitive) is the option UUID. Put changed fields beside those two keys. The direct runner applies the owner check and the existing `OLACLICK_ALLOW_WRITES` gate. [Official variant reference](https://developers.olaclick.app/docs/mcp#update_product_variant).
2. `update_product` renames the parent. The previous legacy `edit_menu` shape combining `variant_id` and `patch.name` triggered that parent operation. Preflight now rejects that shape. For an explicit parent rename, use `edit_menu` with `product_id` and `patch.name`, omitting the variant ID. For both changes, schedule two separate operations in their respective runs.
3. A name-only update sends only `id`, `variantId`, and `name`. For price changes, read the current variant and verify the new effective selling price does not exceed `original_price`. Only send the requested fields. Prices are nonnegative decimals with up to two decimal places. Variant stock counts are nonnegative integers and affect availability only with stock tracking enabled. The MCP variant update has no `description` or `position` field.
4. Check each operation's `orientation.json`. A successful rename must return the requested variant UUID and new name. Re-read the catalogue or use native `list_product_variants` to confirm the final names and unchanged parent names. On an interrupted batch or a 429, read the affected IDs before retrying only missing updates after the backoff. Never recreate existing variants to rename them because orders and drafts refer to their IDs.
