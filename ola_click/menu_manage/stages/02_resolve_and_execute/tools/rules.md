# Menu management — Tool rules

Use `edit_menu` for product text and supported catalogue changes, the dedicated stock intents for availability, and `update_product_variant` for editing a specific variant. Resolve IDs from the catalogue before writing.

## Resolve and verify catalogue targets

| Tool | Scope / kind | Required arguments | Optional arguments | When and how to use |
|---|---|---|---|---|
| [`list_categories`](https://developers.olaclick.app/docs/mcp#list_categories) | `menu:read` / read | — | — | Resolve category UUIDs, visibility and positions, including categories hidden from the menu. |
| [`get_category`](https://developers.olaclick.app/docs/mcp#get_category) | `menu:read` / read | `id` (UUID) | — | Read one category by UUID. Use it to confirm a change in position or visibility. |
| [`list_products`](https://developers.olaclick.app/docs/mcp#list_products) | `menu:read` / read | — | `page` (integer ≥ 1 (default `1`)), `per_page` (integer ≥ 1 ≤ 100 (default `20`)), `category_id` (UUID) | Page through product records, optionally scoped by category. Use get_product for options and modifiers. |
| [`get_product`](https://developers.olaclick.app/docs/mcp#get_product) | `menu:read` / read | `id` (UUID) | — | Read the product, its variants, stock tracking and modifier categories, including limits and required groups. |
| [`list_product_variants`](https://developers.olaclick.app/docs/mcp#list_product_variants) | `menu:read` / read | `id` (UUID) | — | Read the variants of one product and resolve their IDs, prices, SKU and stock. Use for variant rename verification. |
| [`list_kitchens`](https://developers.olaclick.app/docs/mcp#list_kitchens) | `menu:read` / read | — | — | Resolve a valid kitchen UUID before creating a product. |
| `list_modifier_categories` | `menu:read` / read | — | — | Resolve category and modifier IDs, required flags and selection limits. |

## Native catalogue writes

| Tool | Scope / kind | Required arguments | Optional arguments | When and how to use |
|---|---|---|---|---|
| [`update_product`](https://developers.olaclick.app/docs/mcp#update_product) | `menu:write` / write | `product_id` (string) | `name` (string (max 191 chars)), `description` (string) | Edit the product name and/or description. Send at least one of those fields. This never edits a variant. |
| `create_category` † | `menu:write` / write | `name` (string (max 191 chars)) | — | Create a named category. Check list_categories before creating it to avoid a duplicate. |
| [`create_product`](https://developers.olaclick.app/docs/mcp#create_product) | `menu:write` / write | `category_id` (UUID), `kitchen_id` (UUID), `name` (string (max 191 chars)), `variants` (array of object (1–30 items)) with {`name` (string (max 191 chars)) required, `price` (number ≥ 0) required, `original_price` (number ≥ 0) required, `cost` (number ≥ 0), `packaging_price` (number ≥ 0), `sku` (string (max 20 chars)) required, `stock` (integer ≥ 0), `stock_threshold` (integer ≥ 0)} | `description` (string (max 550 chars)), `visible` (boolean), `modifier_category_ids` (array of UUID (0–100 items)) | Resolve the category and kitchen UUIDs. Send 1–30 variants and decimal prices. Images are handled separately. |
| [`create_product_variant`](https://developers.olaclick.app/docs/mcp#create_product_variant) | `menu:write` / write | `id` (UUID), `name` (string (max 191 chars)), `price` (number ≥ 0), `original_price` (number ≥ 0), `sku` (string (max 20 chars)) | `cost` (number ≥ 0), `packaging_price` (number ≥ 0), `stock` (integer ≥ 0), `stock_threshold` (integer ≥ 0) | Add a purchasable option to an existing product. original_price must be at least price. Verify the new variant UUID before ordering. |
| [`update_product_variant`](https://developers.olaclick.app/docs/mcp#update_product_variant) | `menu:write` / write | `id` (UUID), `variantId` (UUID) | `name` (string (max 191 chars)), `price` (number ≥ 0), `original_price` (number ≥ 0), `cost` (number ≥ 0), `packaging_price` (number ≥ 0), `sku` (string (max 20 chars)), `stock` (integer ≥ 0), `stock_threshold` (integer ≥ 0) | Update an existing option by its product UUID and variant UUID. Send at least one change. For a rename send id, variantId and name. Verify the same variant UUID and the new name in the response and re-read when needed. |
| [`sync_product_modifier_categories`](https://developers.olaclick.app/docs/mcp#sync_product_modifier_categories) | `menu:write` / write | `id` (UUID), `modifier_category_ids` (array of UUID (0–100 items)) | — | Replace the entire ordered association list. Read the current product and category list first. Use distinct IDs. An empty array removes all associations. |
| [`create_modifier`](https://developers.olaclick.app/docs/mcp#create_modifier) | `menu:write` / write | `name` (string (max 191 chars)), `original_price` (number ≥ 0), `modifier_category_id` (UUID), `max_limit` (integer ≥ 1), `visible` (boolean) | `price` (number ≥ 0), `sku` (string (max 20 chars)) | Add a modifier to an existing modifier category. price defaults to original_price and cannot exceed it. |
| [`update_modifier`](https://developers.olaclick.app/docs/mcp#update_modifier) | `menu:write` / write | `id` (UUID) | `name` (string (max 191 chars)), `original_price` (number ≥ 0), `price` (number ≥ 0), `max_limit` (integer ≥ 1), `visible` (boolean), `sku` (string (max 20 chars) or null) | Patch a modifier by its own UUID, with at least one changed field. Updating only original_price can also move the selling price if there is no discount. |
| [`update_product_position`](https://developers.olaclick.app/docs/mcp#update_product_position) | `menu:write` / write | `id` (UUID), `position` (integer ≥ 0) | — | Move a product within its current category. Positions start at zero and siblings shift automatically. |
| [`update_category`](https://developers.olaclick.app/docs/mcp#update_category) | `menu:write` / write | `id` (UUID) | `position` (integer ≥ 0), `visible` (boolean) | Change visibility or sibling position. At least one is required. Hiding affects all products in that category. This tool does not rename categories. |
| `delete_category` † | `menu:write` / destructive | `categoryId` (UUID) | — | Delete the verified category by categoryId. Use the local destructive workflow or the panel according to local support. |

## Rename an existing variant

First resolve the product and its variant by a live catalogue read. Set `PRODUCT_ID`, `VARIANT_ID` and `NEW_NAME` from that read and the requested name. `RAW` contains the verbatim request. Preview with `OLACLICK_ALLOW_WRITES=0` if needed. Authorized live operations respect the configured gate.

```sh
o="$MSG/ola_click/02_menu_manage" && mkdir -p "$o" && \
node ola_click/_shared/tools/write-intent.cjs --quiet \
  --out-dir "$o" --raw-text "$RAW" --actor owner --intent update_product_variant \
  --entities "$(node -e 'const [id, variantId, name] = process.argv.slice(1); console.log(JSON.stringify({id, variantId, name}));' -- "$PRODUCT_ID" "$VARIANT_ID" "$NEW_NAME")" && \
node ola_click/_shared/tools/run-stage02.cjs --summary "$o"
```

For multiple variants, put one `{"intent":"update_product_variant","entities":{"id":...,"variantId":...,"name":...}}` per verified pair in the operations array. Pass it with `--operations-file`, inspect each result and confirm the new names in the catalogue.

### Native request

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "update_product_variant",
    "arguments": {
      "id": "11111111-1111-4111-8111-111111111111",
      "variantId": "22222222-2222-4222-8222-222222222222",
      "name": "Frango com requeijão"
    }
  }
}
```

Here `id` is the existing product UUID, while `variantId` comes from that product’s `list_product_variants` or `get_product` response. The values above are illustrative. For a rename, include only the new name besides the two IDs. The same operation also accepts price, original price, cost, packaging, SKU and stock fields. Use major currency units with up to two decimal places and check the effective price pair before updating. [Official variant parameters](https://developers.olaclick.app/docs/mcp#update_product_variant).

- `update_category` accepts only `position` and/or `visible` after `id`. The server also lists `create_category` and `delete_category`. The local ICM blocks category deletion and its bulk import can create categories.
- Modifier creation, modifier updates and association replacement are native capabilities. Use the existing ICM only for the intents listed in its extraction rules.
