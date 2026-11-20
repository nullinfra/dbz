# Company & Users

Handle the authenticated branch profile, active payment methods, and staff directory. Use [Stage 01](stages/01_extract/CONTEXT.md) to extract the request, then [Stage 02](stages/02_resolve_and_execute/CONTEXT.md) to check and execute it.

| Request | Intent |
|---|---|
| Branch details, opening hours or current opening status | `get_company` |
| Payment methods, optionally for one service type | `list_payment_methods` |
| Staff by role or account status | `list_users` |

Use [Clients](../clients/CONTEXT.md) for client profiles and [Menu lookup](../menu_read/CONTEXT.md) for external delivery app status. The [official MCP reference](https://developers.olaclick.app/docs/mcp#company--users) lists supported company and user tools.
