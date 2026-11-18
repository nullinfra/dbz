# Intent classification and entity extraction rules

Decision rules for Stage 01. Follow [tool rules](../tools/rules.md) for exact CLI syntax.

## 1. Action gate (`is_olaclick_action`)

- If the text has **no** OlaClick operation (only greeting, chit-chat, or a pure delivery address with no order/menu/store request), use `intent: "non_actionable"`.
- If the text contains **1** operation, use `--intent` + `--entities`.
- If the text contains **2 or more** operations (e.g. *"têm coca-cola? quero 2 pastéis de carne e vê o estado do pedido #12"* or *"mete o bacalhau out of stock e muda a coxinha para 3€"* or a bulk menu import), use `--operations` as a JSON array of `{"intent": ..., "entities": {...}}`.

## 2. Actor classification (`actor`)

- `customer`: *"quero pedir"*, *"manda 2..."*, *"têm...?"*, *"onde anda o meu pedido?"*, *"estão abertos?"*, *"quanto custa a entrega?"*.
- `owner`: *"mete X out of stock"*, *"já temos X"*, *"muda o preço"*, *"quais pedidos pendentes?"*, *"atribui o estafeta"*, *"quanto vendemos?"*, *"cria promoção"*, *"importa/cria este menu"*.
- `unknown`: ambiguous phrasing.

## 3. Exact `entities` schema per intent

| Intent | Exact `entities` keys |
|---|---|
| `create_order` | `items` (`[{"name": str, "quantity": int, "notes": str?}]`), `service_type` (`"DELIVERY"` / `"TAKEAWAY"` / `"ONSITE"` / `"TABLE"`, `null` if unstated), `delivery_address` (`str?`), `customer_name`, `customer_phone`, `payment_method`, `notes` |
| `update_order` | `order_id`, `items_add`, `items_remove`, `items_update`, `notes` |
| `check_menu_item` | `product_query` (`str`) |
| `cancel_order` | `order_id`, `reason` |
| `set_item_out_of_stock` | `product_query` or `product_id`, `visible` (`bool?`) |
| `restore_item_in_stock` | `product_query` or `product_id`, `stock` (`int?`), `visible` (`true`) |
| `edit_menu` | Single: `product_query` or `product_id`, `patch` (`{"name", "price", "description", "visible", "available", "stock", "category"}`). Bulk: `categories` (`[{"name", "products": [{"name", "price", "description"}]}]`) or `operations` (`[{"action": "create_category"|"create_product"|"update_product", ...}]`) |
| `check_order_status` | `order_id` |
| `quote_delivery` | `delivery_address`, `coordinates` (`{lat, lng}?`) |
| `apply_coupon_or_promo` | `coupon_code`, `order_id` |
| `check_store_hours_or_open` | `{}` (optional `date`) |
| `get_menu_category` | `category_query` (`str`, or `""` for full available menu summary) |
| `manage_customer_address` | `customer_id?`, `customer_name`, `customer_phone`, `delivery_address`, `notes` |
| `advance_order_status` | `order_id`, `new_status` |
| `list_active_orders` | `status?`, `start_date?` (`YYYY-MM-DD`), `end_date?` (`YYYY-MM-DD`) |
| `assign_rider` | `order_id`, `rider_id` or `rider_name` |
| `register_payment` | `order_id`, `payment_method`, `amount?` |
| `sales_summary` | `start_date?` (`YYYY-MM-DD`), `end_date?` (`YYYY-MM-DD`), `metric?` |
| `manage_promotions` | `operation` (`"create"`/`"update"`/`"delete"`), `promotion_id?`, `code`, `discount_percent?`, `discount_amount?`, `active?`, `notes?` |

## 4. Preservation rules

- Keep `raw_text` verbatim. Never invent IDs, prices, or unstated `service_type`.
