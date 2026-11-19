# Back-office operations — Extraction rules

Use this pipeline for checking order status, listing orders, querying sales, analytics or cashier balances, and working with saved delivery addresses. Route staff and standalone client profile requests to [Company & Users](../../../../company_users/CONTEXT.md).

## 1. Intents and exact `entities` schemas

| Intent | When to use | Exact `entities` keys |
|---|---|---|
| `check_order_status` | Customer or owner asks about a specific order's status/details | `order_id` (`str?`, UUID, `"PT-..."`, or daily `#`), `customer_phone?`, `customer_name?` |
| `list_active_orders` | Owner lists orders by status, service type, payment status, or date range | `status`, `service_type`, `payment_status` (`"PAID"` \| `"UNPAID"`), `cancelation_reason?`, `start_date`, `end_date` |
| `sales_summary` | Owner asks sales, top products, analytics, cashier balances, tables, staff users, or webhooks | `start_date`, `end_date`, `report_type` (`"summary"` \| `"by_hour"` \| `"by_day"` \| `"by_service_type"` \| `"by_source"` \| `"top_payments"` \| `"margins"` \| `"product_margins"` \| `"menu_conversion"` \| `"cashier"` \| `"tables"` \| `"users"` \| `"webhooks"`), `include_top_products` (`bool?`), `top_limit` (`int?`) |
| `manage_customer_address` | Look up (`operation: "lookup"`), create, or update a customer profile and delivery address | `operation` (`"lookup"` \| `"upsert"`), `customer_id?`, `customer_name?`, `customer_phone?`, `country_calling_code?`, `email?`, `delivery_address?`, `complement?`, `reference?`, `coordinates?` |

## 2. Edge-Case Extraction Rules

1. **Relative dates (*"hoje"*, *"ontem"*, *"esta semana"*, *"este mês"*):** Leave `start_date: null, end_date: null` for *"hoje"* or omitted dates (the shared executor defaults to today in `Europe/Lisbon`).
2. **Top-selling products (*"qual o prato mais vendido?"*):** Set `include_top_products: true, top_limit: 5`.
3. **Cashier (*"a caixa está aberta?"* / *"saldo de caixa"*):** Use `sales_summary` with `report_type: "cashier"`.
