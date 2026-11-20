# OlaClick — Workflow router

Choose an ICM for each requested operation, pass it the relevant inputs, and collect the results for the caller. Use the [shared resolution contract](references/catalog-resolution.md) for all requests that name or describe targets.

| Request | ICM | Intents |
|---|---|---|
| Start a new order or continue supplying details for its draft | [Order creation](order_create/CONTEXT.md) | `create_order` |
| Change or cancel an existing order, advance its order status, apply a discount, or record payment | [Order modification](order_modify/CONTEXT.md) | `update_order`, `cancel_order`, `advance_order_status`, `apply_coupon_or_promo`, `register_payment` |
| Browse the menu, check an item, price, availability, or external delivery app status | [Menu lookup](menu_read/CONTEXT.md) | `check_menu_item`, `get_menu_category`, `check_store_hours_or_open` |
| Change stock, products, variants, or categories | [Menu management](menu_manage/CONTEXT.md) | `set_item_out_of_stock`, `restore_item_in_stock`, `edit_menu` |
| List, inspect, or manage a promotion campaign | [Promotions](promotions/CONTEXT.md) | `manage_promotions` |
| Quote a delivery fee, assign a rider, or report delivery progress or rider position | [Delivery logistics](logistics_delivery/CONTEXT.md) | `quote_delivery`, `assign_rider`, `update_delivery_status`, `report_rider_position` |
| Look up order status, list orders, run sales reports, or manage a customer address record | [Back-office operations](backoffice_ops/CONTEXT.md) | `check_order_status`, `list_active_orders`, `sales_summary`, `manage_customer_address` |
| Check branch details or hours, accepted payment methods, or staff accounts | [Company & Users](company_users/CONTEXT.md) | `get_company`, `list_payment_methods`, `list_users` |
| List or search clients, view a client profile, or create or update one | [Clients](clients/CONTEXT.md) | `get_clients`, `get_client`, `create_client`, `update_client` |
| No OlaClick action, or an unsupported request | [Routing gates](references/routing_gates.md) | `non_actionable`, `unsupported_request` |

Use [Geolocation](../maps/geolocation_icm/stages/01_extract_and_resolve/CONTEXT.md) for address resolution, distance, or ETA. Check the routing gates for unsupported or owner-only operations.

During an open draft, classify the current request before acting on the draft. A recommendation such as *"qual a melhor sobremesa?"* is `menu_read`. Route answers to pending item choices, new selections, checkout details, and draft changes to `order_create`. Follow the [draft and checkout rules](order_create/stages/01_extract/references/draft.md).

An explicit order for *"um de cada artigo de todo o menu"* is `order_create` with a dependent [catalog lookup and expansion](menu_read/stages/02_resolve_and_execute/tools/rules.md#expand-a-request-for-the-full-catalog). For a named category, use a lookup scoped to that category and expand the verified available products in it. Plain *"um de cada"* uses the relevant offer already shown. When the scope has no clear referent, ask which list or category the customer means.

## Read set (read all docs for the selected ICM(s) in ONE `cat` command)

Stage `CONTEXT.md` files are summarized here and in [ola_click/_shared/tools/rules.md](_shared/tools/rules.md); **there is no `tools/rules.md` in a module unless listed below**. Never `ls`, `find`, or `rg` inside `ola_click/` to discover docs. For combined requests, concatenate the read sets of all selected ICMs into one `cat`.

| ICM | Complete read set (copy-paste into one `cat`) |
|---|---|
| `menu_read` | `cat ola_click/_shared/tools/rules.md ola_click/references/catalog-resolution.md ola_click/menu_read/stages/01_extract/references/extraction.md ola_click/menu_read/stages/02_resolve_and_execute/references/policy.md ola_click/menu_read/stages/02_resolve_and_execute/tools/rules.md` |
| `order_create` | `cat ola_click/_shared/tools/rules.md ola_click/references/catalog-resolution.md ola_click/order_create/stages/01_extract/references/extraction.md ola_click/order_create/stages/01_extract/references/draft.md ola_click/order_create/stages/01_extract/references/menus_and_boxes.md ola_click/order_create/stages/02_resolve_and_execute/references/policy.md` |
| `order_modify` | `cat ola_click/_shared/tools/rules.md ola_click/references/catalog-resolution.md ola_click/order_modify/stages/01_extract/references/extraction.md ola_click/order_modify/stages/02_resolve_and_execute/references/policy.md` |
| `menu_manage` | `cat ola_click/_shared/tools/rules.md ola_click/references/catalog-resolution.md ola_click/menu_manage/stages/01_extract/references/extraction.md ola_click/menu_manage/stages/02_resolve_and_execute/references/policy.md` |
| `promotions` | `cat ola_click/_shared/tools/rules.md ola_click/promotions/stages/01_extract/references/extraction.md ola_click/promotions/stages/02_resolve_and_execute/references/policy.md` |
| `logistics_delivery` | `cat ola_click/_shared/tools/rules.md ola_click/logistics_delivery/stages/01_extract/references/extraction.md ola_click/logistics_delivery/stages/02_resolve_and_execute/references/policy.md` |
| `backoffice_ops` | `cat ola_click/_shared/tools/rules.md ola_click/backoffice_ops/stages/01_extract/references/extraction.md ola_click/backoffice_ops/stages/02_resolve_and_execute/references/policy.md` |
| `company_users` | `cat ola_click/_shared/tools/rules.md ola_click/company_users/stages/01_extract/CONTEXT.md ola_click/company_users/stages/02_resolve_and_execute/CONTEXT.md` |
| `clients` | `cat ola_click/_shared/tools/rules.md ola_click/clients/stages/01_extract/references/extraction.md ola_click/clients/stages/02_resolve_and_execute/references/policy.md` |
| `routing_gates` | `cat ola_click/_shared/tools/rules.md ola_click/references/routing_gates.md` |

## Coordinate the selected ICMs

1. Use the supplied `<message_dir>` (or allocate one from [tools/chat-output.md](../tools/chat-output.md) if none was supplied). Assign each run a numbered subdirectory under `<message_dir>/ola_click/`, e.g. `01_menu_read/`. Independent work may run as a single batch (note: `company_users` and `clients` must be in separate runs from other modules) or as separate concurrent runs (`( run A ) & ( run B ) & wait`). Sequence writes that can affect the same state. When an operation needs an earlier result, wait for the verified result and pass it to the dependent stage.
2. **Stage 01:** Use the unified writer `node ola_click/_shared/tools/write-intent.cjs --quiet ...` documented in [ola_click/_shared/tools/rules.md](_shared/tools/rules.md) — it handles every OlaClick intent (including `company_users` and `clients`).
3. **Stage 02:** Run `node ola_click/_shared/tools/run-stage02.cjs --summary "$ola_out"` in the same shell command after Stage 01. For `create_order`, `run-stage02.cjs` runs the draft check and writes `draft_readiness.json` automatically; do not run `check-draft.cjs` separately with `&&`. **If preflight blocks a batch (`BLOCKED`), immediately re-run the unaffected ready operations in their own run (`02_...`) before replying** — never skip ready operations because another operation in the batch was blocked.
4. Collect the `orientation.json` result (printed in compact form by `--summary`) for each branch or batch and match the operations back to the request order. For an unfinished order, always expand any catalog/offer reference and run `run-stage02.cjs` (with `OLACLICK_ALLOW_WRITES=0` for preview/drafts) before replying — never reply after writing `stage01_intent.json` alone. For a gate-only run, use `write-intent.cjs` followed by `run-stage02.cjs --summary`.
