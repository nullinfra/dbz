# Order creation — Tool rules

Use the `create_order` ICM intent for the draft, preview and submission. These native commands describe the lifecycle used by the executor and the lookups it depends on.

## Order lifecycle

| Tool | Scope / kind | Required arguments | Optional arguments | When and how to use |
|---|---|---|---|---|
| [`list_tables`](https://developers.olaclick.app/docs/mcp#list_tables) | `orders:read` / read | — | — | Read zones and their qrs entries. Use the table entry ID for TABLE orders. |
| [`create_order`](https://developers.olaclick.app/docs/mcp#create_order) | `orders:write` / write | `service_type` (string (`ONSITE`, `TABLE`, `DELIVERY`, `TAKEAWAY`)) | `idempotency_key` (string), `status` (string (`INITIATED`, `PENDING`)), `client_id` (UUID), `address_id` (UUID), `table_id` (UUID), `comment` (string (max 500 chars)), `order_title` (string (max 50 chars)), `delivery_price` (number ≥ 0), `packaging_price` (number ≥ 0), `scheduled_delivery_date` (string) | Resolve the client, table or address UUID as applicable. Omit status to start INITIATED, add the basket, then set PENDING. Reuse the same idempotency key on retry. |
| [`add_order_combos`](https://developers.olaclick.app/docs/mcp#add_order_combos) | `orders:write` / write | `id` (UUID), `combos` (array of object (1–unbounded items)) with {`variant_id` (UUID) required, `quantity` (integer ≥ 1) required, `comment` (string (max 500 chars)), `modifiers` (array of object (default `[]`)) with {`modifier_id` (UUID) required, `quantity` (integer ≥ 1 (default `1`))}} | — | Build lines from verified variants. Send the basket together. Each modifier quantity is per unit of its combo. Read get_product for required modifier groups and limits. |
| [`update_order_status`](https://developers.olaclick.app/docs/mcp#update_order_status) | `orders:write` / write | `id` (UUID), `status` (string (`PENDING`, `PREPARING`, `READY`, `DELIVERED`, `FINALIZED`)) | — | Advance only. Skipping steps applies intervening transitions. Use cancel_order for cancellation. |
| `get_order` | `orders:read` / read | `id` (UUID) | — | Read a single order and its combo, payment and discount IDs. Use the internal UUID, not the customer-facing order number. |

## Preview an order

Use `run-stage02.cjs --summary` directly with write gates set to `0` — it writes `draft_readiness.json`, `preflight.json`, and `orientation.json` in one call:

```sh
OLACLICK_ALLOW_WRITES=0 OLACLICK_ALLOW_DESTRUCTIVE=0 \
  node ola_click/_shared/tools/run-stage02.cjs --summary "$ola_out"
```

A standalone `check-draft.cjs` exits `1` on `DRAFT`. The Stage 02 runner already performs this check. Run Stage 02 even for an unfinished draft so it writes the orientation and readiness files.

## Execute an order

With the draft ready and any required confirmation obtained, run `node ola_click/_shared/tools/run-stage02.cjs --summary "$ola_out"` with the configured write gate. Verify the reference and resulting status before reporting creation. After a partial failure, inspect the order and reuse its create idempotency key on a retry.

- **Order items.** In `add_order_combos`, use `combos: [{"variant_id":"<variant UUID>","quantity":2,"modifiers":[{"modifier_id":"<modifier UUID>","quantity":1}]}]`. That records one modifier per unit, two in total. Product `id`, variant `variant_id` and order line `comboId` identify three different records.
