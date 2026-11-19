# Company & Users

Handle the authenticated branch profile, active payment methods, staff directory, and client profiles. Use [Stage 01](stages/01_extract/CONTEXT.md) to extract the request, then [Stage 02](stages/02_resolve_and_execute/CONTEXT.md) to check and execute it.

| Request | Intent |
|---|---|
| Branch details, opening hours or current opening status | `get_company` |
| Payment methods, optionally for one service type | `list_payment_methods` |
| Staff by role or account status | `list_users` |
| Client search and list | `get_clients` |
| Details of a verified client | `get_client` |
| Create or edit a client profile | `create_client`, `update_client` |

Use [Back-office operations](../backoffice_ops/CONTEXT.md) for saved delivery addresses. Use [Menu lookup](../menu_read/CONTEXT.md) for external delivery app status. The [official MCP reference](https://developers.olaclick.app/docs/mcp#company--users) lists supported company and user tools.
