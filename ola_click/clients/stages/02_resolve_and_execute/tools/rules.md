# Clients — Tool rules

These four native tools have matching ICM intents. Pass only the arguments needed for the verified client search, read or edit.

## Client profiles

| Tool | Scope / kind | Required arguments | Optional arguments | When and how to use |
|---|---|---|---|---|
| [`get_clients`](https://developers.olaclick.app/docs/mcp#get_clients) | `clients:read` / read | — | `page` (integer ≥ 1), `per_page` (integer ≥ 1 ≤ 100), `simple_paginate` (boolean), `sort_by` (string (`name`, `phone_number`, `available_points`, `used_points`, `source`, `total_orders`, `address`)), `direction` (string (`asc`, `desc`)), `include_addresses` (boolean), `filter_name` (string), `filter_phone_number` (string), `filter_country_calling_code` (string), `filter_type` (string), `filter_status` (string), `filter_source` (string), `filter_available_points` (number), `filter_used_points` (number) | Search profiles with filter_* keys. Combine national number with calling code for an exact match and scan pages as needed. |
| `get_client` | `clients:read` / read | `id` (UUID) | — | Read the profile of a verified client UUID. |
| [`create_client`](https://developers.olaclick.app/docs/mcp#create_client) | `clients:write` / write | `name` (string (max 150 chars)), `phone_number` (string (max 20 chars)), `country_calling_code` (string (max 4 chars)) | `email` (string (max 150 chars)) | Check for the phone first. Pass the national number and calling code separately as digit strings. Resolve client_already_exists before retrying. |
| [`update_client`](https://developers.olaclick.app/docs/mcp#update_client) | `clients:write` / write | `id` (UUID) | `name` (string (max 150 chars)), `phone_number` (string (max 20 chars)), `country_calling_code` (string (max 4 chars)), `email` (string (max 150 chars)) | Patch a client by UUID with at least one profile field. Verify any phone change against existing clients. |
