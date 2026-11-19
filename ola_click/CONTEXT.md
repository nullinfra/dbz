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
| Check branch details or hours, accepted payment methods, staff accounts, or client profiles | [Company & Users](company_users/CONTEXT.md) | `get_company`, `list_payment_methods`, `list_users`, `get_clients`, `get_client`, `create_client`, `update_client` |
| No OlaClick action, or an unsupported request | [Routing gates](references/routing_gates.md) | `non_actionable`, `unsupported_request` |

Use [Geolocation](../maps/geolocation_icm/stages/01_extract_and_resolve/CONTEXT.md) for address resolution, distance, or ETA. Check the routing gates for unsupported or owner-only operations.

During an open draft, classify the current request before acting on the draft. A recommendation such as *"qual a melhor sobremesa?"* is `menu_read`. Route answers to pending item choices, new selections, checkout details, and draft changes to `order_create`. Follow the [draft and checkout rules](order_create/stages/01_extract/references/draft.md).

An explicit order for *"um de cada artigo de todo o menu"* is `order_create` with a dependent [catalog lookup and expansion](menu_read/stages/02_resolve_and_execute/tools/rules.md#expand-a-request-for-the-full-catalog). For a named category, use a lookup scoped to that category and expand the verified available products in it. Plain *"um de cada"* uses the relevant offer already shown. When the scope has no clear referent, ask which list or category the customer means.

## Coordinate the selected ICMs

1. Take the current message directory from the [chat output contract](../tools/chat-output.md). Assign each run a numbered subdirectory under `<message_dir>/ola_click/`, including each separate or dependent run. Independent work may run as a single batch or as separate concurrent runs. Sequence writes that can affect the same state. When an operation needs an earlier result, such as applying a coupon to a newly created order, wait for the verified result and pass it to the dependent stage.
2. Give each **Stage 01** the verbatim message, known actor, assigned operations in request order, and upstream results. Keep Company & Users operations in their own run and use its [intent writer](company_users/stages/01_extract/CONTEXT.md). Use the [shared intent writer](_shared/tools/rules.md#write-the-intent) for the other modules.
3. Give each **Stage 02** the exact run directory containing the checked `stage01_intent.json` and its operation scope. Have each selected stage apply its policy, then use the [shared Stage 02 runner](_shared/tools/rules.md#write-the-orientation). If preflight blocks a batch, ask about the affected operations and give unrelated ready operations their own run. Keep dependent operations paused until their prerequisites are verified.
4. Collect the `orientation.json` result for each branch or batch and match the operations back to the request order. For an unfinished order, always expand any catalog/offer reference and run the [draft check and current catalogue reads](order_create/stages/02_resolve_and_execute/CONTEXT.md) (`draft_readiness.json`) before replying — never reply after writing `stage01_intent.json` alone. Use the per-operation results for mixed requests, including any clarification or confirmation. For a gate-only run, use the [intent writer](_shared/tools/rules.md#write-the-intent) followed by the [gate finalizer](_shared/tools/rules.md#write-the-orientation).
