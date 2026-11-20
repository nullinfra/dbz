# Back-office orders and addresses — Tool rules

Use this file for order lookups and saved delivery addresses. The router selects [report tools](reports.md) or [integration tools](integrations.md) for those requests.

The tables use native MCP arguments. For ICM payloads, use the module extraction rules.

## Order and table lookups

| Tool | Scope / kind | Required arguments | Optional arguments | When and how to use |
|---|---|---|---|---|
| [`get_orders`](https://developers.olaclick.app/docs/mcp#get_orders) | `orders:read` / read | — | `order_id` (string), `status` (string (`pending`, `preparing`, `ready`, `delivered`, `finalized`, `cancelled`)), `service_type` (string (`delivery`, `takeaway`, `onsite`, `table`)), `source` (string), `payment_status` (string), `payment_method_ids` (string), `owner_ids` (string), `rider_ids` (string), `delivered_by` (string), `delivery_status` (string), `is_scheduled` (string (`true`, `false`)), `client_id` (string), `public_id` (string), `cancelation_reason` (string), `start_date` (string), `end_date` (string), `start_time` (string), `end_time` (string), `time_type` (string), `timezone` (string (default `"America/Bogota"`)), `page` (integer ≥ 1), `per_page` (integer ≥ 1 ≤ 100) | Search orders by date, status, source or client. Supplying order_id bypasses filters and paging. Use lowercase status/service values. For today set both dates and Europe/Lisbon explicitly. |
| `get_order` | `orders:read` / read | `id` (UUID) | — | Read a single order and its combo, payment and discount IDs. Use the internal UUID, not the customer-facing order number. |
| [`list_tables`](https://developers.olaclick.app/docs/mcp#list_tables) | `orders:read` / read | — | — | Read zones and their qrs entries. Use the table entry ID for TABLE orders. |

## Saved addresses

| Tool | Scope / kind | Required arguments | Optional arguments | When and how to use |
|---|---|---|---|---|
| [`list_addresses`](https://developers.olaclick.app/docs/mcp#list_addresses) | `addresses:read` / read | `client_id` (string) | `per_page` (number), `page` (number) | Read saved addresses for one client. Use the address ID belonging to that client for delivery. |
| [`create_address`](https://developers.olaclick.app/docs/mcp#create_address) | `addresses:write` / write | `client_id` (UUID), `address` (string (max 191 chars)) | `complement` (string (max 100 chars)), `reference` (string (max 100 chars)), `latitude` (number ≥ -90 ≤ 90), `longitude` (number ≥ -180 ≤ 180), `area_id` (UUID or null), `default` (boolean) | Save a street address for a verified client. Coordinates must travel as a pair. area_id identifies a configured delivery area. |
| [`update_address`](https://developers.olaclick.app/docs/mcp#update_address) | `addresses:write` / write | `id` (UUID) | `address` (string (max 191 chars)), `complement` (string (max 100 chars)), `reference` (string (max 100 chars)), `latitude` (number ≥ -90 ≤ 90), `longitude` (number ≥ -180 ≤ 180), `area_id` (UUID or null), `default` (boolean) | Patch the address by UUID. The client owner cannot be changed. Send both coordinates when changing either. |
| [`delete_address`](https://developers.olaclick.app/docs/mcp#delete_address) | `addresses:write` / destructive | `id` (UUID) | — | Delete the verified saved address irreversibly. |

- `get_orders` currently advertises singular `service_type` with lowercase values; its prose mentions plural `service_types`, which is absent from the live argument list. For several service types, make one filtered read per type and merge by order UUID.
