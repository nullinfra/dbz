# Menu management — Extraction rules

Use this pipeline when the restaurant owner manages stock, prices, text, visibility, or imports. Interpret the request using [current catalogue records](../../../../references/catalog-resolution.md). Pass verified product and variant IDs for writes. Use an exact category ID when available.

## 1. Intents and exact `entities` schemas

| Intent | When to use | Exact `entities` keys |
|---|---|---|
| `set_item_out_of_stock` | Mark a product/variant (or all products containing an ingredient) out of stock (`stock: 0`) | `product_id`, `variant_id` (`str?`) |
| `restore_item_in_stock` | Restore a product/variant back in stock (always use this—not `edit_menu`—for *"repor em stock"*, even if the owner states `0` or a negative number, so preflight rejects invalid counts) | `product_id`, `variant_id` (`str?`), `stock` (positive integer supplied by the owner) |
| `edit_menu` (product name/description) | Rename the product itself or update its description | `product_id`, `patch` (`{"name"?, "description"?}`); omit `variant_id` |
| `update_product_variant` (direct MCP) | Edit an existing variant's name, price, cost, packaging price, SKU or stock. Use this for every variant rename. | `id` (product UUID), `variantId` (variant UUID), plus at least one of `name`, `price`, `original_price`, `cost`, `packaging_price`, `sku`, `stock`, `stock_threshold`, all at the top level |
| `edit_menu` (existing price/stock shortcuts and product position) | Adjust variant prices or stock via the legacy workflow, end a variant price promotion, or move a product. Use the dedicated stock intents for marking unavailable/restoring. | `product_id`, `variant_id` for a targeted variant, `patch` (`{"price"?, "original_price"?, "stock"?, "stock_threshold"?, "packaging_price"?, "position"?, "end_promo"?}`) |
| `edit_menu` (create single product/variant) | Add 1 new product to an existing category or 1 new variant to an existing product | `operation` (`"create_product"` \| `"create_variant"`), `category_id` and optional `kitchen_id` for a new product, `product_id` for a new variant, then `name`, `price`, `original_price?`, `description?`, `sku?` |
| `edit_menu` (category manage / bulk price) | Hide/show/reorder a category, or bulk adjust prices in a category (*"+0,50€"*, *"baixa em 2,00 €"* → `price_delta: -2.0`, *"+10%"*) | `category_query` or `category_id`, `patch` (`{"visible"?, "position"?, "price_delta"?, "price_percent"?}`) |
| `edit_menu` (bulk import) | Create/update multiple categories and products at once | `categories` (`[{"name": str, "products": [{"name": str, "price": number, "description"?: str}]}]`) |

## 2. Platform Capability Boundaries & Edge Cases

1. **Changes handled in the OlaClick panel for this ICM** include deleting products or categories, renaming a category, uploading product images, and toggling visibility or stock tracking on an existing product. The upstream catalogue exposes [additional commands and their fields](../../02_resolve_and_execute/tools/rules.md#native-catalogue-writes). `update_category` accepts only `position` and/or `visible`.
2. **Always resolve targets first.** Use a live `menu_read` (`get_menu_category` with `include_details: true`) to locate the product. Verify the target variant belongs to it with `check_menu_item` and `include_details: true`, or native `list_product_variants` (`{"id":"<product UUID>"}`). Keep identity by UUID when names repeat. For a batch rename, map each verified variant to its new name and change only the named variants.
3. **Single ambiguous product vs. group stock changes.** If the owner names a single product that has multiple variants without specifying a variant (and without explicitly asking for all variants), pass `product_id` **without** `variant_id` as one operation so Stage 02 returns `AMBIGUOUS_VARIANT` and asks which variant to update—never expand it into operations for every variant. Only prepare one operation per verified product/variant when the owner explicitly requests multiple products or all variants.

For a rename, use one operation like this, with real UUIDs from the verified read:

```json
{"intent":"update_product_variant","entities":{"id":"11111111-1111-4111-8111-111111111111","variantId":"22222222-2222-4222-8222-222222222222","name":"Frango com requeijão"}}
```

Use `--operations-file` for a list of variant updates. Keep that run separate from legacy `edit_menu` or `get_menu_category` operations. See [execution and verification](../../02_resolve_and_execute/references/policy.md#variant-edits).
