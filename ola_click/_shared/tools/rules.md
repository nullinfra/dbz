# OlaClick tool and command rules

Run all commands from `Restaurante/`. Treat Python tools as black boxes. Set `ola_out` to this run's assigned subdirectory under `<message_dir>/ola_click/`, e.g. `"$MSG/ola_click/01_menu_read"`.

**Critical:** Always pass `--raw-text` as the **exact, character-for-character `<whatsapp>` message** (never paraphrase, trim, or merge with prior turns).

## Canonical one-liner (write + run in one command)

Use the unified writer `ola_click/_shared/tools/write-intent.cjs` for **every** OlaClick intent (it auto-dispatches `company_users`, `clients`, and all other modules) and `run-stage02.cjs --summary` to execute and print a compact summary while writing full artifacts to disk:

```sh
o="$MSG/ola_click/01_menu_read" && mkdir -p "$o" && \
node ola_click/_shared/tools/write-intent.cjs --quiet \
  --out-dir "$o" \
  --raw-text "Quero ver as opções do menu" \
  --actor customer \
  --intent get_menu_category \
  --entities '{"include_details":true}' && \
node ola_click/_shared/tools/run-stage02.cjs --summary "$o"
```

For a batch of independent operations (note: `company_users` and `clients` must be in separate runs from other modules):

```sh
o="$MSG/ola_click/01_batch" && mkdir -p "$o" && \
node ola_click/_shared/tools/write-intent.cjs --quiet \
  --out-dir "$o" \
  --raw-text "<verbatim text>" \
  --actor customer \
  --operations '[{"intent":"get_menu_category","entities":{"include_details":true}},{"intent":"check_store_hours_or_open","entities":{"check_external_apps":true}}]' && \
node ola_click/_shared/tools/run-stage02.cjs --summary "$o"
```

Use `--operations-file <path>` for a large operations array (e.g., bulk menu import).

### Parallel independent runs in one command

When running `company_users` / `clients` alongside another module, or multiple independent runs:

```sh
( o1="$MSG/ola_click/01_payments"; mkdir -p "$o1" && node ola_click/_shared/tools/write-intent.cjs --quiet --out-dir "$o1" --raw-text "$RAW" --actor owner --intent list_payment_methods --entities '{"service_type":"DELIVERY"}' && node ola_click/_shared/tools/run-stage02.cjs --summary "$o1" ) & \
( o2="$MSG/ola_click/02_menu"; mkdir -p "$o2" && node ola_click/_shared/tools/write-intent.cjs --quiet --out-dir "$o2" --raw-text "$RAW" --actor owner --intent get_menu_category --entities '{"include_details":true}' && node ola_click/_shared/tools/run-stage02.cjs --summary "$o2" ) & \
wait
```

## Multi-turn chat context

Instead of `find`, locate prior drafts, `menu_offer.json`, and recent orientations in one command:

```sh
node .codex/chat-output.cjs context "$MSG"
```

## Exit codes

| Tool | Exit `0` | Non-zero exit |
|---|---|---|
| `write-intent.cjs` | `stage01_intent.json` written | Invalid flags, unknown intent, or mixed `company_users`/`clients` with legacy modules |
| `run-stage02.cjs` | `orientation.json` written (`COMPLETED`, `NEEDS_CLARIFICATION`, `UNSUPPORTED_OPERATION`, `NEEDS_CONFIRMATION`, `PLANNED_DRY_RUN`, `NO_ACTION`) | `API_ERROR` or invalid `stage01_intent.json` |
| `check-draft.cjs` | `status: "READY"` | **`status: "DRAFT"` (exits `1`!)** — never chain `check-draft.cjs` with `&&` before `run-stage02.cjs`. `run-stage02.cjs` already runs the draft check and writes `draft_readiness.json` automatically. |
| `menu-offer.cjs` | Path or JSON items printed | Invalid args or unavailable/missing product |

## Preview an order (or unfinished draft)

Use `run-stage02.cjs --summary` directly with write gates set to `0` — it writes `draft_readiness.json`, `preflight.json`, and `orientation.json` in one call:

```sh
OLACLICK_ALLOW_WRITES=0 OLACLICK_ALLOW_DESTRUCTIVE=0 \
  node ola_click/_shared/tools/run-stage02.cjs --summary "$ola_out"
```

## Required `catalog_review` shape (`create_order`, `items_add`, `items_swap`)

Every item requires `product_id`, `name`, `quantity` (>= 1), and `catalog_review` with all 4 keys (`ola_click/_shared/schemas/catalog_review.schema.json`):

```json
"catalog_review": {
  "category_id": "<category UUID from live menu result>",
  "description": "<exact catalogue description string, or null>",
  "groups": [],
  "issues": []
}
```

If there are prose choices, add `{"label":"Bebida","min":1,"max":1,"selections":[],"question":"Qual bebida?"}` to `groups`. If there is an unresolved condition outside group counts, add `{"question":"..."}` to `issues`.

## `menu-offer.cjs` quick reference

- Record shortlist: `node ola_click/menu_read/stages/02_resolve_and_execute/tools/menu-offer.cjs record "$ola_out/orientation.json" "$product_ids_json"`
- Resolve selection (arg 1 is **current** `$MSG`, not `..`): `node ola_click/menu_read/stages/02_resolve_and_execute/tools/menu-offer.cjs select "$MSG" "$offer_file" 'all'` (or `'[1,3]'`)
- Expand full catalog (arg 1 is **current** `$MSG`): `node ola_click/menu_read/stages/02_resolve_and_execute/tools/menu-offer.cjs catalog "$MSG" "$menu_out/orientation.json"`

## Intent → ICM quick map

- `order_create`: `create_order`
- `order_modify`: `update_order`, `cancel_order`, `advance_order_status`, `apply_coupon_or_promo`, `register_payment`
- `menu_read`: `check_menu_item`, `get_menu_category`, `check_store_hours_or_open`
- `menu_manage`: `set_item_out_of_stock`, `restore_item_in_stock`, `edit_menu`
- `promotions`: `manage_promotions`
- `logistics_delivery`: `quote_delivery`, `assign_rider`, `update_delivery_status`, `report_rider_position`
- `backoffice_ops`: `check_order_status`, `list_active_orders`, `sales_summary`, `manage_customer_address`
- `company_users`: `get_company`, `list_payment_methods`, `list_users`
- `clients`: `get_clients`, `get_client`, `create_client`, `update_client`
- `routing_gates`: `non_actionable`, `unsupported_request`

## Orientation contract

| Status | Meaning |
|---|---|
| `COMPLETED` | Action executed and verified. |
| `NEEDS_CLARIFICATION` | Required information is missing, invalid, or ambiguous. |
| `UNSUPPORTED_OPERATION` | A platform or business rule prevents the action. |
| `NEEDS_CONFIRMATION` | A write or destructive action was prepared in dry run. |
| `PLANNED_DRY_RUN` | A read was prepared in dry run without an API key. |
| `NO_ACTION` | The request matched the non-actionable gate. |
| `API_ERROR` | The finalizer reports an upstream error and exits nonzero. |

Use `needs_clarification`, `confirmation_required`, and `suggested_message` when replying. Full details are always in `<run>/orientation.json`.
