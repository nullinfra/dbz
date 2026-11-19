# Order modification — Extraction rules

Use the [resolution contract](../../../../references/catalog-resolution.md) and the verified current order. Read the confirmed order reference and active lines before preparing changes.

| Intent | Entities |
|---|---|
| `update_order` | `order_id`, `items_add` with reviewed catalogue items, `items_remove` with `combo_id` and optional `quantity`, `items_set_quantity` with `combo_id` and target `quantity`, `items_swap` with `combo_id`, optional quantity removed, and a reviewed `replacement` item. Also supports `delivery_price`, `packaging_price`, `notes`, `delivery_comment`, `scheduled_delivery_date`, `ambiguous_notes`, `allergy_notes`, `allergy_review`. |
| `cancel_order` | `order_id`, API `reason` such as `TEST_ORDER`, `WRONG_ORDER`, `DUPLICATED_ORDER`, `REJECTED_ORDER`, `FREE_ORDER` or `OTHER`, plus optional `detail`. Interpret the customer's reason before execution. |
| `advance_order_status` | `order_id` or independent `order_ids`, and `new_status` as `PENDING`, `PREPARING`, `READY`, `DELIVERED` or `FINALIZED`. |
| `apply_coupon_or_promo` | `order_id` with `coupon_code`, or `discount_type` and `discount_value`, or `remove_discount: true` and a verified `discount_id`. |
| `register_payment` | `order_id` and verified `payment_method_id`, optional `amount`, `received_amount`, `tip_amount`. For split payments use `payments` with those fields and an explicit amount on each. For removal use `remove_payment: true` and a verified `payment_id`. |

Use [Company & Users](../../../../company_users/CONTEXT.md) to resolve a payment method from the methods enabled for the order's service. Treat each physical line as distinct when two items have the same name. Review new and replacement items using the [catalogue choice contract](../../../../order_create/stages/01_extract/references/menus_and_boxes.md).
