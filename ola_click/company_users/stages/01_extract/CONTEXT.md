# 01 Extract — Company & Users

## Inputs

- The verbatim request, known actor, operation order, upstream details, and the assigned run directory under the current message's `ola_click/`.
- The [module intents](../../CONTEXT.md) and [official MCP parameters](https://developers.olaclick.app/docs/mcp#tool-reference).

## Process

1. Use `get_company` with `{}` for branch details. Use `list_payment_methods` with `{}` or `{"service_type":"DELIVERY"}` if the customer names a service type. The service type is a local filter and may also be `TAKEAWAY`, `ONSITE` or `TABLE`.
2. For staff, use `list_users` with optional `role`, `active`, `page`, and `per_page`. Roles are comma-separated, e.g. `"manager,cashier"`. Record the status as a JSON boolean. An active account describes permission to use the branch software, so handle questions about staff on duty as a separate fact.

```sh
node ola_click/company_users/stages/01_extract/tools/write-intent.cjs \
  --out-dir "$ola_out" --raw-text "Quais os métodos de pagamento para entrega?" \
  --actor customer --intent list_payment_methods --entities '{"service_type":"DELIVERY"}'
```

Use `--operations '[{"intent":"get_company","entities":{}},{"intent":"list_payment_methods","entities":{}}]'` for independent Company & Users operations. Pass the known actor from chat context. The directory and raw text are required for both forms.

## Output and check

On exit zero, `<run>/stage01_intent.json` contains only assigned `company_users` operations in request order. Pass the same directory to [Stage 02](../02_resolve_and_execute/CONTEXT.md).
