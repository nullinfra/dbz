# Clients — Extraction rules

| Intent | When to use | Exact `entities` keys |
|---|---|---|
| `get_clients` | List, rank, or search profiles | All fields optional. See the filters below. |
| `get_client` | View a specific verified profile | `id` (client UUID) |
| `create_client` | Create a profile | `name`, `phone_number`, `country_calling_code`, optional `email` |
| `update_client` | Change an existing profile | `id` and one or more of `name`, `phone_number`, `country_calling_code`, `email` |

Use the [official MCP tool reference](https://developers.olaclick.app/docs/mcp#company--users).

## Client search

| Fields | Values |
|---|---|
| `filter_name` | Partial name, accent-insensitive |
| `filter_phone_number`, `filter_country_calling_code` | National-number prefix and optional calling code, as strings of digits |
| `filter_type` | Purchase frequency. Comma-separated `ELITE_BUYER`, `TOP_BUYER`, `FREQUENT_BUYER`, `REPEAT_BUYER`, `BUYER`, `NO_BUYER` |
| `filter_status` | Purchase recency. Comma-separated `ACTIVE`, `INACTIVE`, `SLEEPING`, `AT_RISK` |
| `filter_source` | Comma-separated `chatbot`, `ecommerce`, `panel` |
| `filter_available_points`, `filter_used_points` | Numeric thresholds. OlaClick returns clients with more points than the supplied value. |
| `sort_by`, `direction` | Sort by `name`, `phone_number`, `available_points`, `used_points`, `source`, `total_orders`, or `address`, using `asc` or `desc` |
| `page`, `per_page` | Positive page number and page size from 1 to 100. Defaults are 1 and 25. |
| `include_addresses`, `simple_paginate` | JSON booleans. Request addresses only when needed and use regular pagination when the request needs a total. |

Use `get_client` when the owner provides a UUID. Verify the UUID before an update using a recent profile result or a separate `get_client` run. Resolve a name or phone through `get_clients`. A phone filter matches a prefix. For a full phone lookup, verify the exact national number and calling code. If several profiles match, ask the owner which one they mean using only the details needed to distinguish them. If no profile matches, ask for another identifying detail.

## Profile fields

- Capture the name as supplied, up to 150 characters. Use the national number and calling code as separate digit strings and preserve leading zeros. The live MCP schema accepts 6–20 digits for `phone_number` and 1–4 digits for `country_calling_code`.
- Include an email of up to 150 characters when supplied or explicitly changed. For an update, send only the fields the owner asked to change.
- If a required field is missing, keep the details already supplied and ask for that specific field.
