# Menu lookup — Tool rules

Use the shared writer for `get_menu_category`, `check_menu_item` and `check_store_hours_or_open`. The table describes native MCP arguments. ICM filters such as `include_details` are handled by the ICM and are absent from the native call.

## Catalogue and food app reads

| Tool | Scope / kind | Required arguments | Optional arguments | When and how to use |
|---|---|---|---|---|
| [`get_menu`](https://developers.olaclick.app/docs/mcp#get_menu) | `menu:read` / read | — | `category_slug` (string), `available_only` (boolean) | Read the catalogue, availability and prices in major currency units. The category slug comes from the result. Full catalogue is not paginated and excludes products without variants. |
| [`list_categories`](https://developers.olaclick.app/docs/mcp#list_categories) | `menu:read` / read | — | — | Resolve category UUIDs, visibility and positions, including categories hidden from the menu. |
| [`get_category`](https://developers.olaclick.app/docs/mcp#get_category) | `menu:read` / read | `id` (UUID) | — | Read one category by UUID. Use it to confirm a change in position or visibility. |
| [`list_products`](https://developers.olaclick.app/docs/mcp#list_products) | `menu:read` / read | — | `page` (integer ≥ 1 (default `1`)), `per_page` (integer ≥ 1 ≤ 100 (default `20`)), `category_id` (UUID) | Page through product records, optionally scoped by category. Use get_product for options and modifiers. |
| [`get_product`](https://developers.olaclick.app/docs/mcp#get_product) | `menu:read` / read | `id` (UUID) | — | Read the product, its variants, stock tracking and modifier categories, including limits and required groups. |
| [`list_product_variants`](https://developers.olaclick.app/docs/mcp#list_product_variants) | `menu:read` / read | `id` (UUID) | — | Read the variants of one product and resolve their IDs, prices, SKU and stock. Use for variant rename verification. |
| `get_store_status` | `stores:read` / read | — | `provider_names` (string) | Read open status per food app. UNKNOWN is distinct from closed. For the restaurant’s direct channel use get_company. |

## Menu offers

Run from `Restaurante/`. Use this tool when offering a product shortlist that can be ordered by position or as a group. Use a completed menu lookup with `results[].mcp_result.menu_matches` so the offer has exact catalog identities.

## Save the shortlist

Pass the verified product IDs as a JSON array in the exact order you will show them. Save before replying.

```sh
node ola_click/menu_read/stages/02_resolve_and_execute/tools/menu-offer.cjs \
  record "$ola_out/orientation.json" "$offered_product_ids_json"
```

The tool writes `menu_offer.json` beside the orientation and prints its path. Leave it alongside the message that displayed the shortlist.

## Resolve the customer's selection

Use the relevant offer from the same chat. For *"um de cada"* pass `all`. For numbered selections pass a JSON array of 1-based positions such as `'[1,3]'`.

```sh
node ola_click/menu_read/stages/02_resolve_and_execute/tools/menu-offer.cjs \
  select "$message_dir" "$offer_file" all
```

The tool prints an array of order items with the verified product IDs, full OlaClick names and quantity one per selection. Merge explicit quantities and concrete choices into the draft. Stage 02 revalidates current availability before checkout.

## Expand a request for the full catalog

When the customer explicitly orders one of every product on the menu, run an unfiltered `get_menu_category` with `include_details: true` in this message. Pass the completed orientation to the catalog command:

```sh
node ola_click/menu_read/stages/02_resolve_and_execute/tools/menu-offer.cjs \
  catalog "$message_dir" "$menu_out/orientation.json"
```

The result is the list of draft order items. A nonzero exit means the summary could not safely identify all requested items. Resolve incomplete categories or ambiguous names with a detailed menu read. Review the live description and choices for every expanded item through [order creation](../../../../order_create/CONTEXT.md).
