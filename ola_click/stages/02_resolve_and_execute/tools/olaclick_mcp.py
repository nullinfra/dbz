#!/usr/bin/env python3
"""Official OlaClick MCP JSON-RPC client (https://public-api.olaclick.app/mcp)."""
import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ACTION_SPECS: dict[str, dict[str, str]] = {
    "check_menu_item": {"class": "read", "mcp_tool": "get_menu", "scope": "menu:read"},
    "get_menu_category": {"class": "read", "mcp_tool": "get_menu", "scope": "menu:read"},
    "check_store_hours_or_open": {"class": "read", "mcp_tool": "get_store_status", "scope": "menu:read"},
    "check_order_status": {"class": "read", "mcp_tool": "get_order", "scope": "orders:read"},
    "list_active_orders": {"class": "read", "mcp_tool": "get_orders", "scope": "orders:read"},
    "sales_summary": {"class": "read", "mcp_tool": "get_orders_summary", "scope": "orders:read"},
    "quote_delivery": {"class": "read", "mcp_tool": "get_delivery_quote", "scope": "orders:read"},
    "create_order": {"class": "write", "mcp_tool": "create_order+add_order_combos", "scope": "orders:write"},
    "update_order": {"class": "write", "mcp_tool": "update_order", "scope": "orders:write"},
    "advance_order_status": {"class": "write", "mcp_tool": "update_order_status", "scope": "orders:write"},
    "apply_coupon_or_promo": {"class": "write", "mcp_tool": "apply_order_coupon", "scope": "orders:write"},
    "assign_rider": {"class": "write", "mcp_tool": "assign_rider", "scope": "orders:write"},
    "register_payment": {"class": "write", "mcp_tool": "add_order_payment", "scope": "orders:write"},
    "set_item_out_of_stock": {"class": "write", "mcp_tool": "update_product_variant", "scope": "menu:write"},
    "restore_item_in_stock": {"class": "write", "mcp_tool": "update_product_variant", "scope": "menu:write"},
    "edit_menu": {"class": "write", "mcp_tool": "update_product+update_product_variant", "scope": "menu:write"},
    "manage_customer_address": {"class": "write", "mcp_tool": "create_client+create_address", "scope": "customers:write"},
    "manage_promotions": {"class": "write", "mcp_tool": "create_promotion|update_promotion|delete_promotion", "scope": "promotions:write"},
    "cancel_order": {"class": "destructive", "mcp_tool": "cancel_order", "scope": "orders:write"},
}

ALL_SOURCES = "CHATBOT,DIDI,IFOOD,INBOUND,99FOOD,OUTBOUND,PEDIDOSYA,RAPPI,RAPPI_TURBO,UBER_EATS,KEETA,TOTEM,QR,API"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_env() -> None:
    env_path = _repo_root() / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def _resolve_run_dir(run_id: str | None, out_dir: str | None) -> Path:
    if out_dir:
        return Path(out_dir)
    if not run_id:
        active = Path(tempfile.gettempdir()) / "olaclick-icm" / ".active-run"
        if not active.is_file():
            raise RuntimeError("No active run found. Run Stage 01 write_stage01.py --start first.")
        run_id = active.read_text(encoding="utf-8").strip()
    return _repo_root() / "output" / "runs" / run_id


def _mcp_call(mcp_url: str, api_key: str, tool_name: str, arguments: dict[str, Any]) -> tuple[bool, Any]:
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    req = urllib.request.Request(mcp_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            ctype = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8")
            if "text/event-stream" in ctype:
                events = [json.loads(l[5:].strip()) for l in raw.splitlines() if l.startswith("data:") and l[5:].strip()]
                msg = events[-1] if events else {}
            else:
                msg = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return False, {"http_error": exc.code, "detail": exc.read().decode("utf-8", errors="replace")}
    except urllib.error.URLError as exc:
        return False, {"network_error": str(exc.reason)}

    if "error" in msg:
        return False, msg["error"]
    res = msg.get("result") or {}
    is_err = bool(res.get("isError"))
    texts = [c.get("text", "") for c in (res.get("content") or []) if isinstance(c, dict) and c.get("type") == "text"]
    parsed: Any = texts[0] if len(texts) == 1 else texts
    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except json.JSONDecodeError:
            pass
    return (not is_err), parsed


def _extract_menu_categories(menu_data: Any) -> list[dict[str, Any]]:
    if isinstance(menu_data, dict):
        if isinstance(menu_data.get("data"), dict):
            menu_data = menu_data["data"]
        for key in ("categories", "data"):
            if isinstance(menu_data.get(key), list):
                return [c for c in menu_data[key] if isinstance(c, dict)]
        if isinstance(menu_data.get("products"), list):
            return [{"name": "Menu", "products": menu_data["products"]}]
    elif isinstance(menu_data, list):
        return [{"name": "Menu", "products": menu_data}]
    return []


def _is_available(p: dict[str, Any]) -> bool:
    if "available" in p and p["available"] is not None:
        return bool(p["available"])
    return p.get("visible") is not False


def _extract_price(p: dict[str, Any]) -> tuple[Any, str | None, str | None]:
    variants = p.get("variants")
    v0 = variants[0] if isinstance(variants, list) and variants and isinstance(variants[0], dict) else {}
    price = p.get("price") if p.get("price") is not None else v0.get("price")
    currency = p.get("currency") or v0.get("currency")
    return price, currency, v0.get("id")


def _search_menu_matches(menu_data: Any, query: str, by_category: bool = False) -> list[dict[str, Any]]:
    q = query.casefold().strip()
    if not q:
        return []
    matches: list[dict[str, Any]] = []
    for cat in _extract_menu_categories(menu_data):
        cat_name = str(cat.get("name") or "")
        cat_hit = by_category and q in cat_name.casefold()
        for p in cat.get("products") or []:
            if not isinstance(p, dict):
                continue
            name = str(p.get("name") or "")
            if cat_hit or (not by_category and q in name.casefold()):
                price, currency, variant_id = _extract_price(p)
                matches.append(
                    {
                        "id": p.get("id"),
                        "variant_id": variant_id,
                        "category": cat_name or None,
                        "name": name,
                        "price": price,
                        "currency": currency,
                        "available": _is_available(p),
                    }
                )
    return matches


def _summarize_available_menu(menu_data: Any) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for cat in _extract_menu_categories(menu_data):
        cat_name = str(cat.get("name") or "Menu")
        avail_items = []
        for p in cat.get("products") or []:
            if isinstance(p, dict) and _is_available(p):
                price, currency, _ = _extract_price(p)
                avail_items.append({"name": p.get("name"), "price": price, "currency": currency})
        if avail_items:
            summary.append({"category": cat_name, "available_count": len(avail_items), "items": avail_items})
    return summary


def _normalize_service_type(raw: Any) -> str:
    val = str(raw or "DELIVERY").strip().upper()
    aliases = {"PICKUP": "TAKEAWAY", "TAKE_AWAY": "TAKEAWAY", "TAKE-AWAY": "TAKEAWAY", "DINE_IN": "ONSITE", "LOCAL": "ONSITE"}
    val = aliases.get(val, val)
    return val if val in {"ONSITE", "TABLE", "DELIVERY", "TAKEAWAY"} else "DELIVERY"


def _resolve_product_and_variant(entities: dict[str, Any], cached_menu: Any) -> tuple[str | None, str | None]:
    pid = entities.get("product_id")
    vid = entities.get("variant_id")
    if (not pid or not vid) and entities.get("product_query") and cached_menu is not None:
        matches = _search_menu_matches(cached_menu, str(entities["product_query"]))
        if matches:
            pid = pid or matches[0]["id"]
            vid = vid or matches[0]["variant_id"]
    return pid, vid


def _plan_mcp_call(action: str, entities: dict[str, Any], cached_menu: Any) -> tuple[str, str, dict[str, Any]]:
    """Return (tool_class, mcp_tool_name, arguments)."""
    spec = ACTION_SPECS[action]
    tool_class = spec["class"]
    today = datetime.now(ZoneInfo("Europe/Lisbon")).strftime("%Y-%m-%d")
    oid = entities.get("order_id") or "<missing_order_id>"

    if action in {"check_menu_item", "get_menu_category"}:
        return tool_class, "get_menu", {}
    if action == "check_store_hours_or_open":
        return tool_class, "get_store_status", {}
    if action == "check_order_status":
        return tool_class, "get_order", {"id": oid}
    if action == "list_active_orders":
        args: dict[str, Any] = {
            "start_date": str(entities.get("start_date") or today),
            "end_date": str(entities.get("end_date") or today),
            "timezone": "Europe/Lisbon",
        }
        if entities.get("status"):
            args["status"] = str(entities["status"]).upper()
        return tool_class, "get_orders", args
    if action == "sales_summary":
        return tool_class, "get_orders_summary", {
            "start_date": str(entities.get("start_date") or today),
            "end_date": str(entities.get("end_date") or today),
            "sources": ALL_SOURCES,
            "timezone": "Europe/Lisbon",
        }
    if action == "quote_delivery":
        coords = entities.get("coordinates") if isinstance(entities.get("coordinates"), dict) else {}
        args = {k: v for k, v in {"latitude": coords.get("lat"), "longitude": coords.get("lng")}.items() if v is not None}
        return tool_class, "get_delivery_quote", args
    if action == "create_order":
        args = {"service_type": _normalize_service_type(entities.get("service_type")), "idempotency_key": str(uuid.uuid4())}
        comment_parts = []
        if entities.get("delivery_address"):
            comment_parts.append(f"Entrega: {entities['delivery_address']}")
        if entities.get("customer_name"):
            comment_parts.append(f"Cliente: {entities['customer_name']}")
        if entities.get("customer_phone"):
            comment_parts.append(f"Tel: {entities['customer_phone']}")
        if entities.get("notes"):
            comment_parts.append(str(entities["notes"]))
        if comment_parts:
            args["comment"] = " | ".join(comment_parts)[:500]
        return tool_class, "create_order", args
    if action == "update_order":
        args = {"id": oid}
        if entities.get("notes"):
            args["comment"] = entities["notes"]
        return tool_class, "update_order", args
    if action == "advance_order_status":
        return tool_class, "update_order_status", {"id": oid, "status": str(entities.get("new_status") or "").upper()}
    if action == "cancel_order":
        reason = str(entities.get("reason") or "OTHER").upper()
        if reason not in {"REJECTED_ORDER", "TEST_ORDER", "WRONG_ORDER", "FREE_ORDER", "DUPLICATED_ORDER", "OTHER"}:
            args = {"id": oid, "reason": "OTHER", "detail": str(entities.get("reason"))[:200]}
        else:
            args = {"id": oid, "reason": reason}
        return tool_class, "cancel_order", args
    if action == "apply_coupon_or_promo":
        return tool_class, "apply_order_coupon", {"id": oid, "code": str(entities.get("coupon_code") or "")}
    if action == "assign_rider":
        args = {"id": oid, "name": str(entities.get("rider_name") or "Rider")}
        if entities.get("rider_id"):
            args["user_id"] = entities["rider_id"]
        return tool_class, "assign_rider", args
    if action == "register_payment":
        args = {"id": oid, "payment_method_id": entities.get("payment_method_id") or entities.get("payment_method"), "bill_amount": entities.get("amount") or 0}
        return tool_class, "add_order_payment", args
    if action in {"set_item_out_of_stock", "restore_item_in_stock"}:
        pid, vid = _resolve_product_and_variant(entities, cached_menu)
        stock = 0 if action == "set_item_out_of_stock" else int(entities.get("stock") if entities.get("stock") is not None else 99)
        return tool_class, "update_product_variant", {"id": pid or "<resolve>", "variantId": vid or "<resolve>", "stock": stock}
    if action == "edit_menu":
        if isinstance(entities.get("categories"), list):
            cats = entities["categories"]
            return "write", "create_category+create_product", {"categories_count": len(cats)}
        pid, vid = _resolve_product_and_variant(entities, cached_menu)
        patch = entities.get("patch") if isinstance(entities.get("patch"), dict) else {}
        if any(k in patch for k in ("price", "original_price", "stock")):
            args = {"id": pid or "<resolve>", "variantId": vid or "<resolve>"}
            if "price" in patch:
                args["price"] = patch["price"]
                args["original_price"] = patch.get("original_price", patch["price"])
            if "stock" in patch:
                args["stock"] = patch["stock"]
            return tool_class, "update_product_variant", args
        args = {"product_id": pid or "<resolve>"}
        for k in ("name", "description"):
            if k in patch:
                args[k] = patch[k]
        return tool_class, "update_product", args
    if action == "manage_customer_address":
        cid = entities.get("customer_id")
        if cid:
            return tool_class, "update_client", {"id": cid, **{k: entities[k] for k in ("name", "email") if k in entities}}
        return tool_class, "create_client", {"name": entities.get("customer_name") or "", "phone_number": entities.get("customer_phone") or "", "country_calling_code": "+351"}
    if action == "manage_promotions":
        op = str(entities.get("operation") or "create").lower()
        promo_id = entities.get("promotion_id") or "<missing_promotion_id>"
        if op == "delete":
            return "destructive", "delete_promotion", {"id": promo_id}
        if op == "update":
            return "write", "update_promotion", {"id": promo_id}
        return "write", "create_promotion", {"coupon_code": entities.get("code") or "", "discount_value": entities.get("discount_percent") or entities.get("discount_amount") or 0}
    raise ValueError(f"Unsupported action: {action}")


def _execute_create_order(mcp_url: str, api_key: str, entities: dict[str, Any], args: dict[str, Any], cached_menu: Any) -> tuple[bool, Any]:
    ok, order_res = _mcp_call(mcp_url, api_key, "create_order", args)
    if not ok:
        return False, order_res
    order_id = (order_res.get("data") or {}).get("id") if isinstance(order_res, dict) else None
    items = entities.get("items") or []
    combos = []
    for item in items:
        if not isinstance(item, dict):
            continue
        vid = item.get("variant_id")
        if not vid and item.get("name") and cached_menu is not None:
            matches = _search_menu_matches(cached_menu, str(item["name"]))
            if matches:
                vid = matches[0]["variant_id"]
        if vid:
            c: dict[str, Any] = {"variant_id": vid, "quantity": int(item.get("quantity") or 1)}
            if item.get("notes"):
                c["comment"] = str(item["notes"])[:500]
            combos.append(c)
    if order_id and combos:
        ok2, combo_res = _mcp_call(mcp_url, api_key, "add_order_combos", {"id": order_id, "combos": combos})
        if not ok2:
            return False, {"order": order_res, "combos": combo_res}
        ok3, confirm_res = _mcp_call(mcp_url, api_key, "update_order_status", {"id": order_id, "status": "PENDING"})
        return ok3, {"order": confirm_res if ok3 else order_res, "combos": combo_res}
    if order_id:
        ok3, confirm_res = _mcp_call(mcp_url, api_key, "update_order_status", {"id": order_id, "status": "PENDING"})
        return ok3, confirm_res
    return True, order_res


def _execute_bulk_menu(mcp_url: str, api_key: str, entities: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    ok_k, kitchens = _mcp_call(mcp_url, api_key, "list_kitchens", {})
    k_list = (kitchens.get("data") if isinstance(kitchens, dict) else kitchens) or []
    kitchen_id = k_list[0].get("id") if (ok_k and isinstance(k_list, list) and k_list and isinstance(k_list[0], dict)) else None
    if not kitchen_id:
        return False, {"error": "Could not resolve kitchen_id from list_kitchens", "raw": kitchens}

    created_cats, created_prods, errors, tasks = 0, 0, [], []
    for cat in entities.get("categories") or []:
        if not isinstance(cat, dict):
            continue
        ok_c, cat_res = _mcp_call(mcp_url, api_key, "create_category", {"name": cat.get("name")})
        cat_id = (cat_res.get("data") or {}).get("id") if isinstance(cat_res, dict) else None
        if ok_c and cat_id:
            created_cats += 1
            for prod in cat.get("products") or []:
                if isinstance(prod, dict):
                    tasks.append((cat_id, prod))
        else:
            errors.append({"category": cat.get("name"), "error": cat_res})

    def _make_prod(t: tuple[str, dict[str, Any]]) -> tuple[bool, Any, str]:
        cid, p = t
        price = float(p.get("price") or 0)
        sku = uuid.uuid4().hex[:12]
        ok_p, res_p = _mcp_call(
            mcp_url,
            api_key,
            "create_product",
            {
                "category_id": cid,
                "kitchen_id": kitchen_id,
                "name": str(p.get("name") or "")[:191],
                "description": str(p.get("description") or ""),
                "visible": True,
                "variants": [{"name": "Default", "price": price, "original_price": price, "sku": sku}],
            },
        )
        return ok_p, res_p, str(p.get("name"))

    with ThreadPoolExecutor(max_workers=6) as pool:
        for ok_p, res_p, pname in pool.map(_make_prod, tasks):
            if ok_p:
                created_prods += 1
            else:
                errors.append({"product": pname, "error": res_p})
    return len(errors) == 0, {"created_categories": created_cats, "created_products": created_prods, "errors": errors[:20]}


def _run_one(
    op: dict[str, Any],
    mcp_url: str,
    api_key: str,
    has_key: bool,
    allow_writes: bool,
    allow_destructive: bool,
    cached_menu: tuple[bool, Any] | None,
) -> dict[str, Any]:
    action = op["intent"]
    entities = op.get("entities") or {}
    spec = ACTION_SPECS[action]
    menu_body = cached_menu[1] if (cached_menu and cached_menu[0]) else None
    tool_class, mcp_tool, args = _plan_mcp_call(action, entities, menu_body)

    can_execute = has_key and (
        tool_class == "read"
        or (tool_class == "write" and allow_writes)
        or (tool_class == "destructive" and allow_writes and allow_destructive)
    )

    result: dict[str, Any] = {
        "action": action,
        "mcp_tool_class": tool_class,
        "required_scope": spec["scope"],
        "mcp_url": mcp_url,
        "method": "MCP",
        "endpoint": mcp_tool,
        "payload": args,
    }

    if not can_execute:
        reason = "missing_api_key" if not has_key else "safety_gate_disabled"
        result.update({"mode": "dry_run", "dry_run_reason": reason, "http_status": None, "response": None})
        return result

    if action in {"check_menu_item", "get_menu_category"} and cached_menu is not None:
        ok, body = cached_menu
    elif action == "create_order":
        ok, body = _execute_create_order(mcp_url, api_key, entities, args, menu_body)
    elif action == "edit_menu" and isinstance(entities.get("categories"), list):
        ok, body = _execute_bulk_menu(mcp_url, api_key, entities)
    else:
        ok, body = _mcp_call(mcp_url, api_key, mcp_tool, args)

    result.update({"mode": "live", "http_status": 200 if ok else 422, "response": body})
    if ok:
        if action == "check_menu_item":
            result["menu_matches"] = _search_menu_matches(body, str(entities.get("product_query") or ""))
        elif action == "get_menu_category":
            cat_q = str(entities.get("category_query") or "").strip()
            if cat_q:
                result["menu_matches"] = [m for m in _search_menu_matches(body, cat_q, by_category=True) if m["available"]]
            else:
                result["menu_summary"] = _summarize_available_menu(body)
        elif action == "sales_summary":
            result["sales_summary"] = body
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute or dry-run OlaClick official MCP tool(s).")
    parser.add_argument("--action", default=None, choices=sorted(ACTION_SPECS))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    _load_env()
    run_dir = _resolve_run_dir(args.run_id, args.out_dir)
    intent_path = run_dir / "stage01_intent.json"
    if not intent_path.is_file():
        print(f"ERROR: Missing Stage 01 output at {intent_path}", file=sys.stderr)
        return 1

    stage01 = json.loads(intent_path.read_text(encoding="utf-8"))
    operations = (
        [{"intent": args.action, "entities": stage01.get("entities") or {}}]
        if args.action
        else (stage01.get("operations") or [{"intent": stage01["intent"], "entities": stage01.get("entities") or {}}])
    )

    api_key = os.environ.get("OLACLICK_API_KEY", "").strip()
    has_key = bool(api_key) and api_key != "olk_live_replace_me"
    allow_writes = os.environ.get("OLACLICK_ALLOW_WRITES", "0") == "1"
    allow_destructive = os.environ.get("OLACLICK_ALLOW_DESTRUCTIVE", "0") == "1"
    mcp_url = os.environ.get("OLACLICK_MCP_URL", "https://public-api.olaclick.app/mcp")

    needs_menu = any(
        op["intent"] in {"check_menu_item", "get_menu_category", "create_order", "set_item_out_of_stock", "restore_item_in_stock", "edit_menu"}
        and not (op["intent"] == "edit_menu" and isinstance((op.get("entities") or {}).get("categories"), list))
        for op in operations
    )
    cached_menu = _mcp_call(mcp_url, api_key, "get_menu", {}) if (has_key and needs_menu) else None

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(operations)))) as pool:
        results = list(
            pool.map(
                lambda op: _run_one(op, mcp_url, api_key, has_key, allow_writes, allow_destructive, cached_menu),
                operations,
            )
        )

    output: dict[str, Any] = {"run_id": stage01["run_id"], "operations_count": len(results), "results": results}
    if len(results) == 1:
        output.update(results[0])
    (run_dir / "mcp_raw_output.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    compact = []
    for r in results:
        cr = dict(r)
        if r.get("action") in {"check_menu_item", "get_menu_category"} and r.get("http_status") == 200:
            cr["response"] = "<omitted_raw_menu>"
        compact.append(cr)
    print(json.dumps({"run_id": stage01["run_id"], "operations_count": len(compact), "results": compact}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
