# Menu lookup — Extraction rules

Use the [catalogue resolution contract](../../../../references/catalog-resolution.md) when interpreting product names, categories, or food preferences.

| Intent | Entities |
|---|---|
| `get_menu_category` | `category_id` or verified exact `category_query`. Omit both for all visible categories. Use `include_details: true` for catalogue discovery, `min_price` and `max_price` as numbers, `cheapest` to sort candidates, and `only_unavailable` to select availability explicitly. |
| `check_menu_item` | Verified `product_id` or a verified exact `product_query`. Use `include_details: true` to read the product's variant and modifier definitions. |
| `check_store_hours_or_open` | `check_external_apps: true` for external app status. For branch hours and current opening status use [Company & Users](../../../../company_users/CONTEXT.md). |

Use the detailed catalogue to interpret a request such as “algo vegetariano” or “um sumo de maracujá”. Compare descriptions, categories and variant prices and report any uncertain ingredients. When the customer asks for a shortlist, preserve the exact order and IDs of the results shown. Treat a request for a recommendation as advice until the customer selects an item.
