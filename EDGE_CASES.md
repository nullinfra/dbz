# Edge Cases Covered — DoBrasil Pastéis (OlaClick + Geolocation ICM)

This register links the [OlaClick modules](ola_click/CONTEXT.md) and [Geolocation](maps/geolocation_icm/stages/01_extract_and_resolve/CONTEXT.md) to the checks that deal with ambiguous or incomplete requests.

## 1. Language and catalogue identity

The [catalogue resolution contract](ola_click/references/catalog-resolution.md) covers multilingual language, shorthand, missing accents, product codes and ingredient requests. The agent resolves these against live names and descriptions, then carries the selected IDs. Hidden categories are filtered using current category IDs and visibility.

## 2. Order creation and checkout

The [choice review](ola_click/order_create/stages/01_extract/references/menus_and_boxes.md) covers variants, composites, box totals, alternatives, frozen acknowledgements, applicable days, notes and allergies. The agent records questions and selected options. The draft check verifies the resulting groups and quantities, and the executor verifies current product, variant and modifier IDs.

The [checkout policy](ola_click/order_create/stages/02_resolve_and_execute/references/policy.md) covers ambiguous notes, service type, destination, store hours, schedule, partial checkout and cash change. Repeats and substitutions use reviewed current selections.

## 3. Existing orders, status and payments

The [order modification policy](ola_click/order_modify/stages/02_resolve_and_execute/references/policy.md) covers exact order and line references, kitchen state, quantities, swaps, source, status progression, discounts and payments. Known lines carry their original modifiers and notes when the quantity changes.

## 4. Menu Read, Menu Management, Promotions, Logistics & Backoffice

| Pipeline | General Rule / Mechanism | Edge Cases Covered |
|---|---|---|
| **`menu_read`** | Parametric catalog filters | Numeric budgets, availability and catalogue IDs. The agent resolves dietary selections from descriptions. External delivery app status uses `get_store_status`. |
| **`menu_manage`** | Write safety & MCP capability guards | `AMBIGUOUS_PRODUCT`, `AMBIGUOUS_VARIANT`, `STOCK_TRACKING_DISABLED_ON_PRODUCT`, `PRODUCT_VISIBILITY_NOT_IN_MCP`, `FAVORITE_CATEGORY_IMMUTABLE`, `CATEGORY_NOT_EMPTY` on `delete_category`, `original_price >= price` enforcement, duplicate product check on `create_product`, bulk price delta/%, `end_promo`, `stock_threshold`, `update_product_position`, bulk `categories` dedup |
| **`promotions`** | Code/name lookup & date guards | Use selected promotion UUID and live product IDs for product restrictions, `valid_until > valid_from` (`INVALID_DATE_RANGE`), pause via `published: false`, destructive gate on `delete_promotion` |
| **`logistics_delivery`** | Coverage & delivery state guards | Out-of-coverage trap (`price == 0, area == null` flagged as `out_of_coverage: true`, not free delivery), non-delivery order block (`NOT_A_DELIVERY_ORDER`), `NO_RIDER_ASSIGNED` before `DELIVERING` / `report_rider_position`, `DELIVERY_ALREADY_COMPLETED`, `INVALID_COORDINATES` |
| **`backoffice_ops`** | Auth, date validation & analytics | Customer blocked from owner actions (`UNAUTHORIZED_ACTOR`), `start_date > end_date` (`INVALID_DATE_RANGE`), `list_active_orders` (`payment_status`, `cancelation_reason`), `manage_customer_address` (`lookup` with addresses), `sales_summary` (`cashier`, `tables`, `users`, `webhooks`, `margins`, `product_margins`, `by_hour`, `by_day`, `by_service_type`, `by_source`, `top_payments`, `menu_conversion`) |
| **`maps/geolocation_icm`** | Geolocation & route policy | Unstated locality bias, door-number `ROOFTOP` verification, multiple street matches, alternative addresses, POI confirmation, 50 km driving distance threshold |

---

## 5. Remaining Gaps & Additional Edge Cases Worth Considering

### Partially wired in code (next to close)
1. **Duplicate coupon codes.** OlaClick handles uniqueness. Use a verified promotion record before retrying an unclear write.

### New edge cases not yet covered
1. **WhatsApp media / non-text inputs:** customer sends a voice note, photo of a handwritten address, or WhatsApp Location Pin (lat/lng) instead of text.
2. **Same-customer duplicate order / double-send protection:** customer sends the exact same order message twice within 2 minutes (different `idempotency_key` per run unless derived deterministically from `phone + items + 2min_bucket`).
3. **Cross-ICM `maps` → `ola_click` automatic coordinate handoff:** when a customer orders for delivery with a street address, automatically feeding `maps/geolocation_icm`'s resolved `(lat, lng)` + `sub_premise_notes` into `ola_click`'s `create_order` without the LLM re-typing them.
4. **Order total & receipt sanity check before `PENDING`:** verifying `order.total` after `add_order_combos` + `delivery_price` matches expectations, or handling partial combo failures (if item 1 succeeds and item 2 fails in `add_order_combos`, rolling back/canceling the `INITIATED` draft).
5. **90-day analytics range guard & pagination:** warning when `get_orders` hits `per_page` pagination limits (`has_more: true`) on busy days so `list_active_orders` doesn't silently truncate orders.
6. **Table / QR validation on `ONSITE` vs `TABLE`:** when a customer scans/mentions a table QR name that doesn't match `list_tables`, or asks to merge/transfer tables.
