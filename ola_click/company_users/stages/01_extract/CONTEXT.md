# 01 Extract — Company & Users

## Inputs

- The verbatim request, known actor, operation order, verified client or upstream details, and the assigned run directory under the current message's `ola_click/`.
- The [module intents](../../CONTEXT.md) and [official MCP parameters](https://developers.olaclick.app/docs/mcp#tool-reference).

## Process

1. Use `get_company` with `{}` for branch details. Use `list_payment_methods` with `{}` or `{"service_type":"DELIVERY"}` if the customer names a service type. The service type is a local filter and may also be `TAKEAWAY`, `ONSITE` or `TABLE`.
2. For staff, use `list_users` with optional `role`, `active`, `page`, and `per_page`. Roles are comma-separated, e.g. `"manager,cashier"`. Record the status as a JSON boolean. An active account describes permission to use the branch software, so handle questions about staff on duty as a separate fact.
3. For client search, use the documented `get_clients` filters. Preserve the distinction between frequency (`filter_type`) and recency (`filter_status`). For a phone lookup, put the national number and calling code in the corresponding fields. Phone searches match prefixes. Verify the exact phone and country code before choosing one client. For `get_client` or `update_client`, use the verified client UUID as `id`. Resolve names through a separate lookup first.
4. For `create_client`, capture `name`, `phone_number`, `country_calling_code`, and `email` if supplied. For `update_client`, include `id` and only the requested changes. Format phone and calling code as strings of digits. Ask for missing details and clarify ambiguous clients.

```sh
node ola_click/company_users/stages/01_extract/tools/write-intent.cjs \
  --out-dir "$ola_out" --raw-text "Quais os métodos de pagamento para entrega?" \
  --actor customer --intent list_payment_methods --entities '{"service_type":"DELIVERY"}'
```

Use `--operations '[{"intent":"get_company","entities":{}},{"intent":"list_payment_methods","entities":{}}]'` for independent Company & Users operations. Pass the known actor from chat context. The directory and raw text are required for both forms.

## Output and check

On exit zero, `<run>/stage01_intent.json` contains only assigned `company_users` operations in request order. Pass the same directory to [Stage 02](../02_resolve_and_execute/CONTEXT.md).
