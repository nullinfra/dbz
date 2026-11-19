# Menu management — Extraction rules

Use this pipeline when the restaurant owner manages stock, prices, text, visibility, or imports. Interpret the request using [current catalogue records](../../../../references/catalog-resolution.md). Pass verified product and variant IDs for writes. Use an exact category ID when available.

## 1. Intents and exact `entities` schemas

| Intent | When to use | Exact `entities` keys |
|---|---|---|
| `set_item_out_of_stock` | Mark a product/variant (or all products containing an ingredient) out of stock (`stock: 0`) | `product_id`, `variant_id` (`str?`) |
| `restore_item_in_stock` | Restore a product/variant back in stock | `product_id`, `variant_id` (`str?`), `stock` (positive integer supplied by the owner) |
| `edit_menu` (single product/variant) | Change `name`/`description`, variant `price`/`original_price`/`stock`/`stock_threshold`/`packaging_price`, `position`, or `end_promo: true` | `product_id`, `variant_id` (`str?`), `patch` (`{"name"?, "description"?, "price"?, "original_price"?, "stock"?, "stock_threshold"?, "packaging_price"?, "position"?, "end_promo"?}`) |
| `edit_menu` (create single product/variant) | Add 1 new product to an existing category or 1 new variant to an existing product | `operation` (`"create_product"` \| `"create_variant"`), `category_id` and optional `kitchen_id` for a new product, `product_id` for a new variant, then `name`, `price`, `original_price?`, `description?`, `sku?` |
| `edit_menu` (category manage / bulk price) | Hide/show/reorder/delete a category, or bulk adjust prices in a category (*"+0,50€"*, *"+10%"*) | `category_query` or `category_id`, `operation` (`"delete_category"`?), `patch` (`{"visible"?, "position"?, "price_delta"?, "price_percent"?}`) |
| `edit_menu` (bulk import) | Create/update multiple categories and products at once | `categories` (`[{"name": str, "products": [{"name": str, "price": number, "description"?: str}]}]`) |

## 2. Platform Capability Boundaries & Edge Cases

1. **Changes handled in the OlaClick panel** include deleting products or categories, uploading product images, and toggling visibility or stock tracking on an existing product.
2. **Group stock changes.** Resolve the scope with the owner when ambiguous. Prepare one operation per verified product and variant.
