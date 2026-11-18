# Stage 01 tool and command rules

Run all commands from the project root (`Restaurante/`). Never read any `.py` file; this document specifies the exact input/output contract of `write_stage01.py`.

## Single-operation command

```sh
python3 ola_click/stages/01_classify_and_extract/tools/write_stage01.py \
  --start \
  --raw-text "<verbatim text>" \
  --actor <customer|owner|unknown> \
  --intent <intent> \
  --entities '<JSON object>'
```

## Multi-operation command (2+ calls in one message)

```sh
python3 ola_click/stages/01_classify_and_extract/tools/write_stage01.py \
  --start \
  --raw-text "<verbatim text>" \
  --actor <customer|owner|unknown> \
  --operations '[{"intent":"check_menu_item","entities":{"product_query":"coca-cola"}},{"intent":"quote_delivery","entities":{"delivery_address":"Rua X"}}]'
```

For very large payloads (e.g., full menu import), write the JSON array to a file and pass `--operations-file <path>`.

## Allowed `--intent` values
- Core: `create_order`, `update_order`, `check_menu_item`, `cancel_order`, `set_item_out_of_stock`, `edit_menu`
- Customer: `check_order_status`, `quote_delivery`, `apply_coupon_or_promo`, `check_store_hours_or_open`, `get_menu_category`, `manage_customer_address`
- Owner: `advance_order_status`, `list_active_orders`, `assign_rider`, `restore_item_in_stock`, `register_payment`, `sales_summary`, `manage_promotions`
- Gate: `non_actionable`

## Output (`stage01_intent.json` + stdout)
Writes `ola_click/output/runs/<run_id>/stage01_intent.json` with `run_id`, `raw_text`, `is_olaclick_action`, `actor`, `intent`, `entities`, and normalized `operations: [...]`. Exits `0` on valid input.
