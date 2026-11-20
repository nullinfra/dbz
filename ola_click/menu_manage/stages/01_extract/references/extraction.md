# Menu management — Extraction rules

Use this pipeline when the restaurant owner manages stock, prices, text, visibility, or imports. Interpret the request using [current catalogue records](../../../../references/catalog-resolution.md). Pass verified product and variant IDs for writes. Use an exact category ID when available.

## 1. Intents and exact `entities` schemas

| Intent | When to use | Exact `entities` keys |
|---|---|---|
| `set_item_out_of_stock` | Mark a product/variant (or all products containing an ingredient) out of stock (`stock: 0`) | `product_id`, `variant_id` (`str?`) |
| `restore_item_in_stock` | Restore a product/variant back in stock (always use this—not `edit_menu`—for *"repor em stock"*, even if the owner states `0` or a negative number, so preflight rejects invalid counts) | `product_id`, `variant_id` (`str?`), `stock` (positive integer supplied by the owner) |
| `edit_menu` (single product/variant) | Change `name`/`description`, variant `price`/`original_price`/`stock`/`stock_threshold`/`packaging_price`, `position`, or `end_promo: true` | `product_id`, `variant_id` (`str?`), `patch` (`{"name"?, "description"?, "price"?, "original_price"?, "stock"?, "stock_threshold"?, "packaging_price"?, "position"?, "end_promo"?}`) |
| `edit_menu` (create single product/variant) | Add 1 new product to an existing category or 1 new variant to an existing product | `operation` (`"create_product"` \| `"create_variant"`), `category_id` and optional `kitchen_id` for a new product, `product_id` for a new variant, then `name`, `price`, `original_price?`, `description?`, `sku?` |
| `edit_menu` (category manage / bulk price) | Hide/show/reorder/delete a category, or bulk adjust prices in a category (*"+0,50€"*, *"+10%"*) | `category_query` or `category_id`, `operation` (`"delete_category"`?), `patch` (`{"visible"?, "position"?, "price_delta"?, "price_percent"?}`) |
| `edit_menu` (bulk import) | Create/update multiple categories and products at once | `categories` (`[{"name": str, "products": [{"name": str, "price": number, "description"?: str}]}]`) |

## 2. Platform Capability Boundaries & Edge Cases

1. **Changes handled in the OlaClick panel** include deleting products or categories, uploading product images, and toggling visibility or stock tracking on an existing product.
2. **Always resolve targets first.** Before extracting `set_item_out_of_stock`, `restore_item_in_stock`, or `edit_menu` for a named product, run a live `menu_read` (`get_menu_category` with `include_details: true`) to obtain the exact `product_id` (even if `stock_enabled` is `false`—Stage 02 will inspect `get_product` and report `STOCK_TRACKING_DISABLED_ON_PRODUCT`).
3. **Single ambiguous product vs. group stock changes.** If the owner names a single product that has multiple variants without specifying a variant (and without explicitly asking for all variants), pass `product_id` **without** `variant_id` as one operation so Stage 02 returns `AMBIGUOUS_VARIANT` and asks which variant to update—never expand it into operations for every variant. Only prepare one operation per verified product/variant when the owner explicitly requests multiple products or all variants.
