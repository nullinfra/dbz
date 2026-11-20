# Delivery logistics — Extraction rules

Use this pipeline for delivery pricing/quotes, assigning or unassigning a rider, updating delivery tracking status, and reporting rider GPS coordinates.

## 1. Intents and exact `entities` schemas

| Intent | When to use | Exact `entities` keys |
|---|---|---|
| `quote_delivery` | Check delivery pricing rules or quote fee for an address/coordinates | `delivery_address` (`str?`), `coordinates` (`{"lat": number, "lng": number}?`), `district_id` (`str?`) |
| `assign_rider` | Assign or unassign a rider to a delivery order | `order_id` (`str?`), `rider_name` (`str?`), `rider_id` (`str?`), `rider_phone` (`str?`), `provider` (`"api"` \| `"olaclick"`), `unassign` (`bool?`), `customer_name?`, `customer_phone?` |
| `update_delivery_status` | Update physical delivery status (*"a caminho"*, *"chegou"*, *"entregue"*) | `order_id` (`str?`), `delivery_status` (`"DELIVERY_PENDING"` \| `"REQUESTING_RIDER"` \| `"RIDER_ASSIGNED"` \| `"ON_THE_WAY_TO_PICK_UP"` \| `"AT_PICK_UP_PLACE"` \| `"DELIVERING"` \| `"ARRIVED_AT_DELIVERY"` \| `"DELIVERED"` \| `"CANCELED"` \| `"DELIVERY_ISSUE"`), `customer_name?`, `customer_phone?` |
| `report_rider_position` | Report current GPS coordinates of the assigned rider | `order_id` (`str?`), `rider_name` (`str?`), `latitude` (`number?`), `longitude` (`number?`) |

## 2. Edge-Case Extraction Rules

1. **Delivery status natural-language mapping:**
   - *"saiu para entrega"* / *"a caminho"* → `"DELIVERING"`
   - *"chegou à morada"* / *"à porta"* → `"ARRIVED_AT_DELIVERY"`
   - *"entregue"* → `"DELIVERED"`
   - *"a caminho do restaurante"* → `"ON_THE_WAY_TO_PICK_UP"`
   - *"no restaurante"* → `"AT_PICK_UP_PLACE"`
   - *"problema na entrega"* → `"DELIVERY_ISSUE"`
2. **Unassigning a rider (*"tira o estafeta do pedido X"*):**
   - Use `intent: "assign_rider"` with `entities: {"order_id": ..., "unassign": true}`.
3. **District/zone-only fee questions (*"distrito de Coroios"*, *"entrega para Corroios"*):** Do **not** put the district name in `delivery_address` (that blocks preflight without calling pricing). Use `quote_delivery` with `{}` (or a verified `district_id`) so Stage 02 calls `get_delivery_pricing` and resolves the district—even if the customer misspelled the district name.
4. Leave unresolved order references and GPS coordinates null. Use the [resolution policy](../../02_resolve_and_execute/references/policy.md) to find the correct delivery zone or staff rider. The API also accepts `RIDER_NOT_FOUND` and `REQUEST_FAILED` from the delivery provider.
