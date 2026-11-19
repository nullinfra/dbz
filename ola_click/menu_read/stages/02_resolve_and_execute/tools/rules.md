# Save and resolve a menu offer

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
