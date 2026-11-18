# OlaClick ICM — Text to Order & Menu Operations

Processes any incoming text (from a **customer** or **restaurant owner**) into a validated, deterministic OlaClick MCP/API orientation or execution under `ola_click/output/runs/<run_id>/`. Supports **single or multi-operation** requests in one run with parallel execution in Stage 02.

## Pipeline

```text
01_classify_and_extract  ──►  02_resolve_and_execute
  raw text → 1..N ops           shared menu lookup, parallel MCP/API,
  (stage01_intent.json)         policy gates → orientation.json
```

| Stage | Contract | Output (in `ola_click/output/runs/<run_id>/`) |
|---|---|---|
| `01_classify_and_extract` | [CONTEXT.md](stages/01_classify_and_extract/CONTEXT.md) | `stage01_intent.json` |
| `02_resolve_and_execute` | [CONTEXT.md](stages/02_resolve_and_execute/CONTEXT.md) | `orientation.json` |

## Supported intents (19 actions + gate)

- **Core:** `create_order`, `update_order`, `check_menu_item`, `cancel_order`, `set_item_out_of_stock`, `edit_menu` (single or bulk `categories`)
- **Customer:** `check_order_status`, `quote_delivery`, `apply_coupon_or_promo`, `check_store_hours_or_open`, `get_menu_category`, `manage_customer_address`
- **Owner:** `advance_order_status`, `list_active_orders`, `assign_rider`, `restore_item_in_stock`, `register_payment`, `sales_summary`, `manage_promotions`
- **Gate:** `non_actionable` — texto sem ação OlaClick

## Rules
- Run all commands from the project root (`Restaurante/`).
- Treat all `.py` files as black-box tools; never read `.py` files during a run.
- Never write `stages/*/output/`; all run artifacts live in `ola_click/output/runs/<run_id>/`.
