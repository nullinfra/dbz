# Company and users — Tool rules

These three native tools have matching ICM intents. The ICM can filter payment methods for a service, while native `list_payment_methods` takes no arguments.

## Company, payments and staff

| Tool | Scope / kind | Required arguments | Optional arguments | When and how to use |
|---|---|---|---|---|
| [`get_company`](https://developers.olaclick.app/docs/mcp#get_company) | `companies:read` / read | — | — | Read branch identity, business hours and company open status in its timezone. |
| [`list_payment_methods`](https://developers.olaclick.app/docs/mcp#list_payment_methods) | `payment-methods:read` / read | — | — | Read active methods and choose one enabled for the order service. |
| [`list_users`](https://developers.olaclick.app/docs/mcp#list_users) | `users:read` / read | — | `active` (boolean), `role` (string), `per_page` (integer ≥ 1 ≤ 100 (default `20`)), `page` (integer ≥ 1 (default `1`)) | Page through staff, optionally filtering by roles and active status. Use active riders for internal assignments. |
