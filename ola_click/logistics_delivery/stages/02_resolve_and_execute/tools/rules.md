# Delivery logistics — Tool rules

Use the delivery logistics intents. Native arguments such as `id`, `user_id` and `name` map to verified order and rider details from the module. Fetch pricing mode before quoting delivery.

## Delivery fee tools

| Tool | Scope / kind | Required arguments | Optional arguments | When and how to use |
|---|---|---|---|---|
| [`get_delivery_pricing`](https://developers.olaclick.app/docs/mcp#get_delivery_pricing) | `orders:read` / read | — | — | Read the pricing mode first. Use configured FIXED or BY_DISTRICT prices directly when the address or district is eligible. |
| [`get_delivery_quote`](https://developers.olaclick.app/docs/mcp#get_delivery_quote) | `orders:read` / read | — | `district_id` (string), `longitude` (number), `latitude` (number) | Use coordinates together for area, distance or range, or district_id from pricing when applicable. Zero with a null area can indicate accepted delivery outside the configured area, so inspect coverage before quoting. |

## Rider and delivery status tools

| Tool | Scope / kind | Required arguments | Optional arguments | When and how to use |
|---|---|---|---|---|
| [`assign_rider`](https://developers.olaclick.app/docs/mcp#assign_rider) | `logistics:write` / write | `id` (UUID), `name` (string (max 100 chars)) | `phone_number` (string (max 20 chars)), `user_id` (UUID), `provider` (string (`api`, `olaclick`) (default `"api"`)) | For an active internal rider use provider olaclick and user_id from list_users. For an external rider use provider api and the rider details. |
| `unassign_rider` | `logistics:write` / destructive | `id` (UUID) | — | Remove the current rider from the delivery order. Confirm the assignment was removed. |
| [`update_delivery_status`](https://developers.olaclick.app/docs/mcp#update_delivery_status) | `logistics:write` / write | `id` (UUID), `delivery_status` (string (`DELIVERY_PENDING`, `REQUESTING_RIDER`, `RIDER_ASSIGNED`, `RIDER_NOT_FOUND`, `REQUEST_FAILED`, `ON_THE_WAY_TO_PICK_UP`, `AT_PICK_UP_PLACE`, `DELIVERING`, `ARRIVED_AT_DELIVERY`, `DELIVERED`, `CANCELED`, `DELIVERY_ISSUE`)) | — | Change delivery progress using the delivery enum. The order lifecycle uses update_order_status separately. |
| `report_rider_position` | `logistics:write` / write | `id` (UUID), `name` (string (max 191 chars)), `latitude` (number ≥ -90 ≤ 90), `longitude` (number ≥ -180 ≤ 180) | — | Check the assigned rider and use the order UUID, rider name and decimal latitude and longitude. |
