# Order creation — Extraction rules

Use `create_order` when a customer starts or continues an order. Follow the [catalogue resolution contract](../../../../references/catalog-resolution.md) and review [current menu choices](menus_and_boxes.md) for each line.

## Entities

- `items` contains the product `name`, `product_id`, positive integer `quantity`, optional `variant_id`, `modifiers`, `catalog_review`, `notes`, and `recipient`. Before resolution, preserve the customer's words and confirmed choices in the draft. A checkout line requires the catalogue identity and review. A conditional fallback must be requested by the customer and reviewed as a catalogue product before using it.
- Use `ambiguous_notes` and `ambiguous_quantities` for details that could apply to several lines. Split a line when only some units have a customization.
- Use `service_type` with `TAKEAWAY`, `TABLE`, `ONSITE` or `DELIVERY` when known. Carry `table_id` or a verified exact `table_name` for table orders. For delivery carry `delivery_address`, `sub_premise_notes`, and confirmed `coordinates` when available.
- Carry `customer_id` and `address_id` when verified. Keep `customer_name`, `customer_phone`, and `country_calling_code` from the customer as needed. Store the national phone number and country calling code separately as digit strings. If the country is uncertain, ask. Set optional `payment_method` to the confirmed payment preference, `cash_tendered` as a number, and `scheduled_delivery_date` as an ISO-8601 timestamp with offset.
- Preserve `allergy_notes` and use `allergy_review: {"confirmed":true,"source":"..."}` only after restaurant verification. Use `notes` for order-wide requests such as napkins.
- When the customer asks for the same order again, use `repeat_last_order: true` while the prior basket is being found. Require a verified prior order for that customer. Expand its lines, review the current catalogue, and confirm any change of product, variant or choices. Submit the resulting `items` using the same rules as a new basket.

See [draft and checkout](draft.md) for multi-turn selection and questions.
