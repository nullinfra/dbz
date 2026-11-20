# Back-office integrations — Tool rules

Load only for integration requests. The existing back-office ICM documents a webhook listing route. Use the native commands through an authorised client for other integration operations where no ICM intent is registered.

## Webhooks

| Tool | Scope / kind | Required arguments | Optional arguments | When and how to use |
|---|---|---|---|---|
| `list_webhooks` | `webhooks:read` / read | — | — | Read subscriptions for this company and resolve their UUIDs. |
| `get_webhook` | `webhooks:read` / read | `id` (UUID) | — | Inspect one subscription by UUID. Keep any configured header secrets out of chat and logs. |
| [`create_webhook`](https://developers.olaclick.app/docs/mcp#create_webhook) | `webhooks:write` / write | `webhook_url` (string), `merchant_id` (string (max 64 chars)) | `webhook_headers` (object (default `{}`)), `max_retry` (integer ≥ 0 ≤ 10 (default `3`)), `ack_http_codes` (array of integer ≥ 100 ≤ 599 (default `[200, 201, 202]`)), `event_types` (array of string (`ORDER_CREATED`, `ORDER_UPDATED`, `ORDER_DELETED`, `CONNECTION_CREATED`, `CONNECTION_DESTROYED`, `FISCAL_NOTES_REQUEST`)) | Register the merchant’s HTTPS endpoint and merchant identifier. Omit event_types for all events. Use the authorised destination. |
| [`update_webhook`](https://developers.olaclick.app/docs/mcp#update_webhook) | `webhooks:write` / write | `id` (UUID) | `webhook_url` (string), `webhook_headers` (object), `is_active` (boolean), `max_retry` (integer ≥ 0 ≤ 10), `ack_http_codes` (array of integer ≥ 100 ≤ 599), `event_types` (array of string (`ORDER_CREATED`, `ORDER_UPDATED`, `ORDER_DELETED`, `CONNECTION_CREATED`, `CONNECTION_DESTROYED`, `FISCAL_NOTES_REQUEST`)) | Patch one subscription. is_active false pauses deliveries while retaining the subscription. |
| [`delete_webhook`](https://developers.olaclick.app/docs/mcp#delete_webhook) | `webhooks:write` / destructive | `id` (UUID) | — | Remove one subscription. Event deliveries to it stop immediately. |

## Connector connections

| Tool | Scope / kind | Required arguments | Optional arguments | When and how to use |
|---|---|---|---|---|
| `list_conections` | `conections:read` / read | — | — | Resolve the connector’s active connection records. Keep the API spelling conection. |
| `update_conection_status` | `conections:write` / write | `id` (UUID), `status` (string (`active`, `rejected`, `in_provider_review`, `awaiting_company_confirmation`)) | — | Set the requested status for the verified connection UUID. |

- The webhook schema advertises `webhook_headers` as an object, but the returned schema has no declared keys and disallows extra properties. Check the current schema before configuring custom headers. Never include secrets in documentation or logs.
