#!/usr/bin/env python3
"""Official OlaClick MCP client with deterministic pipeline resolution & edge-case guards."""
import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
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
    "check_store_hours_or_open": {"class": "read", "mcp_tool": "get_company", "scope": "companies:read"},
    "check_order_status": {"class": "read", "mcp_tool": "get_order", "scope": "orders:read"},
    "list_active_orders": {"class": "read", "mcp_tool": "get_orders", "scope": "orders:read"},
    "sales_summary": {"class": "read", "mcp_tool": "get_orders_summary", "scope": "orders:read"},
    "quote_delivery": {"class": "read", "mcp_tool": "get_delivery_pricing", "scope": "orders:read"},
    "create_order": {"class": "write", "mcp_tool": "create_order+add_order_combos", "scope": "orders:write"},
    "update_order": {"class": "write", "mcp_tool": "update_order", "scope": "orders:write"},
    "advance_order_status": {"class": "write", "mcp_tool": "update_order_status", "scope": "orders:write"},
    "apply_coupon_or_promo": {"class": "write", "mcp_tool": "apply_order_coupon", "scope": "orders:write"},
    "assign_rider": {"class": "write", "mcp_tool": "assign_rider|unassign_rider", "scope": "logistics:write"},
    "update_delivery_status": {"class": "write", "mcp_tool": "update_delivery_status", "scope": "logistics:write"},
    "report_rider_position": {"class": "write", "mcp_tool": "report_rider_position", "scope": "logistics:write"},
    "register_payment": {"class": "write", "mcp_tool": "add_order_payment", "scope": "orders:write"},
    "set_item_out_of_stock": {"class": "write", "mcp_tool": "update_product_variant", "scope": "menu:write"},
    "restore_item_in_stock": {"class": "write", "mcp_tool": "update_product_variant", "scope": "menu:write"},
    "edit_menu": {"class": "write", "mcp_tool": "update_product|update_product_variant|update_category", "scope": "menu:write"},
    "manage_customer_address": {"class": "write", "mcp_tool": "create_client+create_address", "scope": "clients:write"},
    "manage_promotions": {"class": "write", "mcp_tool": "get_active_promotions|create_promotion|update_promotion|delete_promotion", "scope": "promotions:write"},
    "cancel_order": {"class": "destructive", "mcp_tool": "cancel_order", "scope": "orders:write"},
    "unsupported_request": {"class": "read", "mcp_tool": "none", "scope": "none"},
}

OWNER_ONLY_INTENTS = {
    "set_item_out_of_stock",
    "restore_item_in_stock",
    "edit_menu",
    "advance_order_status",
    "assign_rider",
    "update_delivery_status",
    "report_rider_position",
    "register_payment",
    "list_active_orders",
    "sales_summary",
}

ALL_SOURCES = "CHATBOT,DIDI,IFOOD,INBOUND,99FOOD,OUTBOUND,PEDIDOSYA,RAPPI,RAPPI_TURBO,UBER_EATS,KEETA,TOTEM,QR,API"
STATUS_ORDER = ["INITIATED", "PENDING", "PREPARING", "READY", "DELIVERED", "FINALIZED"]

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


def _norm(text: Any) -> str:
    return unicodedata.normalize("NFC", str(text or "").strip()).casefold()


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


def _extract_menu_categories(menu_data: Any, visible_category_ids: set[str] | None = None) -> list[dict[str, Any]]:
    if isinstance(menu_data, dict):
        if isinstance(menu_data.get("data"), dict):
            menu_data = menu_data["data"]
        for key in ("categories", "data"):
            if isinstance(menu_data.get(key), list):
                cats = [c for c in menu_data[key] if isinstance(c, dict)]
                if visible_category_ids is not None:
                    cats = [c for c in cats if str(c.get("id") or "") in visible_category_ids]
                return cats
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


def _catalog_items(
    menu_data: Any, visible_categories: set[str] | None = None, category: str = ""
) -> list[dict[str, Any]]:
    matches: dict[str, dict[str, Any]] = {}
    key = _norm(category)
    for cat in _extract_menu_categories(menu_data, visible_categories):
        cid, name = str(cat.get("id") or ""), str(cat.get("name") or "")
        if key and key not in {_norm(cid), _norm(name)}:
            continue
        for product in cat.get("products") or []:
            if not isinstance(product, dict) or not product.get("id"):
                continue
            pid = str(product["id"])
            price, currency, variant = _extract_price(product)
            matches.setdefault(pid, {
                "id": pid, "variant_id": variant, "category_id": cid,
                "category": name, "name": product.get("name"),
                "description": product.get("description"), "price": price,
                "currency": currency, "available": _is_available(product),
                "variants": product.get("variants") or [],
                "variants_count": len(product.get("variants") or []),
                "modifier_category_ids": product.get("modifier_category_ids") or [],
            })
    return list(matches.values())


def _search_menu_matches(
    menu_data: Any, query: str, by_category: bool = False, visible_category_ids: set[str] | None = None
) -> list[dict[str, Any]]:
    key = _norm(query)
    if not key:
        return []
    products = _catalog_items(menu_data, visible_category_ids, category=query if by_category else "")
    return [{**product, "exact_match": True} for product in products
            if by_category or key in {_norm(product.get("id")), _norm(product.get("name"))}]


def _resolve_single_product(
    menu_data: Any, query: str, visible_category_ids: set[str] | None = None
) -> tuple[dict[str, Any] | None, str | None, list[dict[str, Any]]]:
    matches = _search_menu_matches(menu_data, query, visible_category_ids=visible_category_ids)
    if len(matches) == 1:
        return matches[0], None, matches
    return None, "AMBIGUOUS_ITEM" if matches else "ITEM_NOT_FOUND", matches


def _summarize_available_menu(menu_data: Any, visible_category_ids: set[str] | None = None) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for cat in _extract_menu_categories(menu_data, visible_category_ids):
        cat_name = str(cat.get("name") or "Menu")
        avail_items = []
        for p in cat.get("products") or []:
            if isinstance(p, dict) and _is_available(p):
                price, currency, _ = _extract_price(p)
                avail_items.append({"name": p.get("name"), "price": price, "currency": currency})
        if avail_items:
            summary.append({"category": cat_name, "available_count": len(avail_items), "items": avail_items})
    return summary


def _resolve_variants_and_modifiers(
    mcp_url: str, api_key: str, prod: dict[str, Any], item: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None]:
    """Validate preselected IDs against the live product and its native constraints."""
    variants = [v for v in prod.get("variants", []) if isinstance(v, dict) and v.get("id")]
    variant_id = item.get("variant_id")
    selected = [v for v in variants if v["id"] == variant_id] if variant_id else variants
    if len(selected) != 1:
        return None, [], "AMBIGUOUS_VARIANT" if not variant_id else "INVALID_VARIANT"
    variant = selected[0]
    mods = item.get("modifiers") if item.get("modifiers") is not None else []
    if not isinstance(mods, list):
        return variant, [], "INVALID_MODIFIER"
    if len(variants) == 1 and not prod.get("modifier_category_ids"):
        return variant, [], "INVALID_MODIFIER" if mods else None

    ok, response = _mcp_call(mcp_url, api_key, "get_product", {"id": prod["id"]})
    detail = response.get("data") if ok and isinstance(response, dict) else None
    groups = detail.get("modifier_categories") if isinstance(detail, dict) else None
    if not isinstance(groups, list) or not set(prod.get("modifier_category_ids") or []).issubset(
        {group.get("id") for group in groups if isinstance(group, dict)}
    ):
        return variant, [], "PRODUCT_OPTIONS_UNVERIFIED"
    current = [v for v in detail.get("variants") or [] if isinstance(v, dict) and v.get("id") == variant["id"]]
    if len(current) != 1:
        return variant, [], "INVALID_VARIANT"
    variant = current[0]
    if detail.get("stock_enabled") is True and isinstance(variant.get("stock"), (int, float)) and variant["stock"] < item["quantity"]:
        return variant, [], "ITEM_UNAVAILABLE"

    options = {}
    quantities = {}
    for group in groups:
        if not isinstance(group, dict):
            continue
        for modifier in group.get("modifiers") or []:
            if isinstance(modifier, dict) and modifier.get("id") and modifier.get("visible") is not False:
                options[modifier["id"]] = (group.get("id"), modifier)
    validated = []
    seen = set()
    price = float(variant.get("price") or 0)
    for entry in mods:
        if not isinstance(entry, dict):
            return variant, [], "INVALID_MODIFIER"
        mid, count = entry.get("modifier_id"), entry.get("quantity")
        if not isinstance(mid, str) or mid not in options or mid in seen or type(count) is not int or count < 1:
            return variant, [], "INVALID_MODIFIER"
        group_id, modifier = options[mid]
        if type(modifier.get("max_limit")) is int and modifier["max_limit"] > 0 and count > modifier["max_limit"]:
            return variant, [], "INVALID_MODIFIER_QUANTITY"
        quantities[group_id] = quantities.get(group_id, 0) + count
        price += float(modifier.get("price") or 0) * count
        seen.add(mid)
        validated.append({"modifier_id": mid, "quantity": count})
    for group in groups:
        if not isinstance(group, dict):
            continue
        count = quantities.get(group.get("id"), 0)
        minimum = int(group.get("min_modifiers") or 0)
        maximum = int(group.get("max_modifiers") or 0)
        if (count or group.get("required")) and count < max(int(bool(group.get("required"))), minimum):
            return variant, [], "MISSING_ITEM_CHOICES"
        if maximum > 0 and count > maximum:
            return variant, [], "INVALID_MODIFIER_QUANTITY"
    return {**variant, "price": price}, validated, None


def _combo_entry(
    mcp_url: str, api_key: str, product: dict[str, Any], item: dict[str, Any], catalog: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any] | None, float, str | None]:
    if not product.get("available"):
        return None, 0, "ITEM_UNAVAILABLE"
    qty = item.get("quantity")
    if type(qty) is not int or qty < 1:
        return None, 0, "INVALID_QUANTITY"
    review = item.get("catalog_review")
    if not isinstance(review, dict) or review.get("issues") != [] or not isinstance(review.get("groups"), list):
        return None, 0, "CATALOG_REVIEW_REQUIRED"
    if ("description" not in review or review["description"] != product["description"] or
            review.get("category_id") != product["category_id"] or item.get("name") != product["name"]):
        return None, 0, "CATALOG_CHANGED"
    variant, modifiers, error = _resolve_variants_and_modifiers(mcp_url, api_key, product, item)
    if error or variant is None:
        return None, 0, error

    choice_labels = []
    for group in review["groups"]:
        if not isinstance(group, dict) or not isinstance(group.get("selections"), list):
            return None, 0, "INVALID_ITEM_CHOICES"
        count = 0
        for choice in group["selections"]:
            if not isinstance(choice, dict) or not isinstance(choice.get("name"), str) or not choice["name"].strip():
                return None, 0, "INVALID_ITEM_CHOICES"
            quantity = choice.get("quantity")
            if type(quantity) is not int or quantity < 1:
                return None, 0, "INVALID_ITEM_CHOICES"
            if choice.get("product_id") is not None:
                candidate = catalog.get(str(choice["product_id"]))
                if not candidate or candidate["name"] != choice["name"] or not candidate["available"]:
                    return None, 0, "ITEM_CHOICE_UNAVAILABLE"
            count += quantity
            choice_labels.append(f"{quantity} × {choice['name']}" if quantity > 1 else choice["name"])
        minimum, maximum = group.get("min"), group.get("max")
        if type(minimum) is not int or minimum < 0 or (maximum is not None and (type(maximum) is not int or maximum < minimum)):
            return None, 0, "INVALID_ITEM_CHOICES"
        if count < minimum or (maximum is not None and count > maximum):
            return None, 0, "INVALID_ITEM_CHOICES"

    notes = []
    if item.get("recipient"):
        notes.append(f"Para: {item['recipient']}")
    if choice_labels:
        notes.append("Opções: " + ", ".join(choice_labels))
    if item.get("notes"):
        notes.append(str(item["notes"]))
    combo = {"variant_id": variant["id"], "quantity": qty, "product_name": product["name"], "modifiers": modifiers}
    if notes:
        comment = " | ".join(notes)
        if len(comment) > 500:
            return None, 0, "ITEM_COMMENT_TOO_LONG"
        combo["comment"] = comment
    return combo, float(variant.get("price") or 0) * qty, None


def _is_uuid(val: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", val.strip()))


def _resolve_order(
    mcp_url: str, api_key: str, entities: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    identifier = str(entities.get("order_id") or "").strip().lstrip("#")
    today = datetime.now(ZoneInfo("Europe/Lisbon")).date().isoformat()

    def get_one(order_id: str) -> tuple[dict[str, Any] | None, str | None, str | None]:
        ok, response = _mcp_call(mcp_url, api_key, "get_order", {"id": order_id})
        order = response.get("data") if ok and isinstance(response, dict) else None
        if isinstance(order, dict) and _norm(order.get("id")) == _norm(order_id):
            return order, None, None
        return None, "ORDER_NOT_FOUND", "Confirma a referência desse pedido."

    if identifier and _is_uuid(identifier):
        return get_one(identifier)
    if not identifier and not (entities.get("customer_phone") or entities.get("customer_name")):
        return None, "ORDER_REFERENCE_REQUIRED", "Qual é a referência do pedido?"

    public_id = identifier if identifier and not identifier.isdigit() else None
    query = {"public_id": public_id} if public_id else {
        "start_date": today, "end_date": today, "timezone": "Europe/Lisbon",
    }
    ok, result = _mcp_call(mcp_url, api_key, "get_orders", {**query, "per_page": 100})
    rows = result.get("data") if ok and isinstance(result, dict) else None
    if not isinstance(rows, list):
        return None, "ORDER_LOOKUP_UNVERIFIED", "Não consegui confirmar a referência do pedido."
    if (result.get("pagination") or {}).get("has_more") is True:
        return None, "ORDER_REFERENCE_REQUIRED", "Indica o código completo ou o identificador do pedido."

    orders = [row for row in rows if isinstance(row, dict) and row.get("id")]
    if public_id:
        matches = [row for row in orders if _norm(row.get("public_id")) == _norm(public_id)]
    elif identifier:
        matches = [row for row in orders if str(row.get("daily_id")) == identifier]
    else:
        phone = str(entities.get("customer_phone") or "")
        name = _norm(entities.get("customer_name"))
        matches = []
        for row in orders:
            client = row.get("client") if isinstance(row.get("client"), dict) else {}
            if str(row.get("status") or "").upper() in {"FINALIZED", "DELIVERED", "CANCELLED"}:
                continue
            if (phone and str(client.get("phone_number") or "") != phone) or (name and _norm(client.get("name")) != name):
                continue
            matches.append(row)

    if len(matches) == 1:
        return get_one(matches[0]["id"])
    if not matches:
        return None, "ORDER_NOT_FOUND", "Não encontrei um pedido com esses dados. Confirma a referência."
    return None, "AMBIGUOUS_ORDER", "Há mais de um pedido com esses dados. Qual é a referência completa?"



def _lookup_exact_client(mcp_url: str, api_key: str, entities: dict[str, Any]) -> tuple[bool, Any]:
    phone = entities.get("customer_phone")
    country = entities.get("country_calling_code")
    if not isinstance(phone, str) or not re.fullmatch(r"\d{6,20}", phone) or not isinstance(country, str) or not re.fullmatch(r"\d{1,4}", country):
        return False, {"error": "CLIENT_PHONE_UNVERIFIED"}
    ok, response = _mcp_call(mcp_url, api_key, "get_clients", {
        "filter_phone_number": phone, "filter_country_calling_code": country, "per_page": 100,
    })
    rows = response.get("data") if ok and isinstance(response, dict) else None
    if not isinstance(rows, list):
        return False, response
    matches = [row for row in rows if isinstance(row, dict) and row.get("id")
               and str(row.get("phone_number")) == phone and str(row.get("country_calling_code")) == country]
    if len(matches) > 1 or (response.get("pagination") or {}).get("has_more"):
        return False, {"error": "CLIENT_ID_UNVERIFIED"}
    return True, matches[0] if matches else None


def _run_create_order_pipeline(
    entities: dict[str, Any],
    mcp_url: str,
    api_key: str,
    has_key: bool,
    allow_writes: bool,
    menu_body: Any,
    visible_cats: set[str] | None,
    company_data: dict[str, Any] | None,
) -> dict[str, Any]:
    base_res: dict[str, Any] = {
        "action": "create_order",
        "mcp_tool_class": "write",
        "required_scope": "orders:write",
        "mcp_url": mcp_url,
        "method": "MCP",
        "endpoint": "create_order+add_order_combos",
    }

    if company_data and company_data.get("currently_open") is False and not entities.get("scheduled_delivery_date"):
        return {**base_res, "mode": "validation", "clarification_reason": "STORE_CLOSED_SCHEDULE_REQUIRED", "suggested_message": "A loja está fechada neste momento e só aceita pedidos agendados. Para que dia e hora queres agendar?"}

    sched = entities.get("scheduled_delivery_date")
    if sched:
        try:
            sched_dt = datetime.fromisoformat(str(sched).replace("Z", "+00:00"))
            if sched_dt < datetime.now(sched_dt.tzinfo or ZoneInfo("Europe/Lisbon")):
                return {**base_res, "mode": "validation", "clarification_reason": "INVALID_SCHEDULE_TIME", "suggested_message": "A hora agendada está no passado. Indica uma data/hora futura."}
        except ValueError:
            return {**base_res, "mode": "validation", "clarification_reason": "INVALID_SCHEDULE_TIME", "suggested_message": "Formato de data/hora agendada inválido."}

    stype = entities.get("service_type")
    items = entities.get("items") or []
    if not items:
        code = "REPEAT_ORDER_REVIEW_REQUIRED" if entities.get("repeat_last_order") else "MISSING_ORDER_ITEMS"
        return {**base_res, "mode": "validation", "clarification_reason": code}
    if entities.get("allergy_notes"):
        review = entities.get("allergy_review")
        if not isinstance(review, dict) or not isinstance(review.get("source"), str) or not review["source"].strip() or review.get("confirmed") is not True:
            return {**base_res, "mode": "validation", "clarification_reason": "ALLERGY_REVIEW_REQUIRED",
                    "suggested_message": "É preciso confirmar os alergénios deste pedido com o restaurante."}
    if not has_key:
        return {**base_res, "mode": "dry_run", "dry_run_reason": "missing_api_key", "http_status": None}
    if menu_body is None or visible_cats is None:
        return {**base_res, "mode": "live", "http_status": 502, "response": {"error": "CATALOG_UNAVAILABLE"}}

    resolved_combos = []
    clarifications = []
    estimated_items_total = 0.0
    catalog = {row["id"]: row for row in _catalog_items(menu_body, visible_cats)}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("product_id"), str) or not _is_uuid(item["product_id"]):
            clarifications.append({"name": item.get("name") if isinstance(item, dict) else None, "code": "PRODUCT_ID_REQUIRED"})
            continue
        product = catalog.get(item["product_id"])
        if product is None:
            clarifications.append({"name": item.get("name"), "code": "ITEM_NOT_FOUND"})
            continue
        combo, total, error = _combo_entry(mcp_url, api_key, product, item, catalog)
        if error:
            clarifications.append({"name": product["name"], "code": error})
            continue
        resolved_combos.append(combo)
        estimated_items_total += total
    if clarifications:
        codes = {entry["code"] for entry in clarifications}
        return {**base_res, "mode": "validation",
                "clarification_reason": codes.pop() if len(codes) == 1 else "MULTIPLE_CLARIFICATIONS",
                "candidates": clarifications}
    if stype not in {"ONSITE", "TABLE", "DELIVERY", "TAKEAWAY"}:
        return {**base_res, "mode": "validation", "clarification_reason": "MISSING_SERVICE_TYPE"}
    if stype == "DELIVERY" and not entities.get("delivery_address"):
        return {**base_res, "mode": "validation", "clarification_reason": "MISSING_DELIVERY_ADDRESS"}

    delivery_price = 0.0
    coords = entities.get("coordinates") if isinstance(entities.get("coordinates"), dict) else {}
    if has_key and stype == "DELIVERY" and coords.get("lat") is not None and coords.get("lng") is not None:
        ok_q, q_res = _mcp_call(mcp_url, api_key, "get_delivery_quote", {"latitude": float(coords["lat"]), "longitude": float(coords["lng"])})
        if ok_q and isinstance(q_res, dict) and isinstance(q_res.get("data"), dict) and q_res["data"].get("price") is not None:
            delivery_price = float(q_res["data"]["price"])

    est_total = estimated_items_total + delivery_price
    if entities.get("cash_tendered") is not None and float(entities["cash_tendered"]) < est_total:
        return {
            **base_res,
            "mode": "validation",
            "clarification_reason": "INSUFFICIENT_CASH_TENDERED",
            "suggested_message": f"O total estimado é {est_total:.2f} €, pelo que {entities['cash_tendered']} € não chega. Confirmas o valor em dinheiro?",
        }

    comment_parts = []
    if entities.get("delivery_address"):
        addr_txt = str(entities["delivery_address"])
        if entities.get("sub_premise_notes"):
            addr_txt += f" ({entities['sub_premise_notes']})"
        comment_parts.append(f"Entrega: {addr_txt}")
    if entities.get("customer_name"):
        comment_parts.append(f"Cliente: {entities['customer_name']}")
    if entities.get("customer_phone"):
        comment_parts.append(f"Tel: {entities['customer_phone']}")
    if entities.get("payment_method"):
        pm_txt = str(entities["payment_method"])
        if entities.get("cash_tendered") is not None:
            pm_txt += f" (troco p/ {entities['cash_tendered']}€)"
        comment_parts.append(f"Pagamento: {pm_txt}")
    if entities.get("notes"):
        comment_parts.append(str(entities["notes"]))

    order_args: dict[str, Any] = {"service_type": stype, "idempotency_key": str(uuid.uuid4())}
    if delivery_price > 0 and stype == "DELIVERY":
        order_args["delivery_price"] = delivery_price
    if sched:
        order_args["scheduled_delivery_date"] = sched
    if comment_parts:
        order_args["comment"] = " | ".join(comment_parts)[:500]

    base_res["payload"] = {"order": order_args, "combos": resolved_combos, "estimated_total": round(est_total, 2)}
    if not (has_key and allow_writes):
        reason = "missing_api_key" if not has_key else "safety_gate_disabled"
        return {**base_res, "mode": "dry_run", "dry_run_reason": reason, "http_status": None, "response": None}

    if stype == "TABLE":
        t_name = str(entities.get("table_id") or entities.get("table_name") or "").strip()
        ok_t, t_res = _mcp_call(mcp_url, api_key, "list_tables", {})
        zones = (t_res.get("data") if isinstance(t_res, dict) else []) if ok_t else []
        matches = {qr["id"] for zone in zones if isinstance(zone, dict)
                   for qr in (zone.get("qrs") or []) if isinstance(qr, dict) and qr.get("id")
                   and _norm(t_name) in {_norm(qr.get("name")), _norm(qr["id"])}}
        if len(matches) != 1:
            return {**base_res, "mode": "validation", "clarification_reason": "MISSING_TABLE", "suggested_message": "Indica o número da mesa (ex.: Mesa 1, Mesa 2, Mesa 3)."}
        order_args["table_id"] = matches.pop()

    cid = entities.get("customer_id")
    if isinstance(cid, str) and _is_uuid(cid):
        order_args["client_id"] = cid
    elif entities.get("customer_phone") and entities.get("country_calling_code") and entities.get("customer_name"):
        ok_c, client = _lookup_exact_client(mcp_url, api_key, entities)
        if not ok_c:
            return {**base_res, "mode": "live", "http_status": 422, "response": client}
        if client is None:
            ok_c, response = _mcp_call(mcp_url, api_key, "create_client", {
                "name": entities["customer_name"], "phone_number": entities["customer_phone"],
                "country_calling_code": entities["country_calling_code"],
            })
            client = response.get("data") if ok_c and isinstance(response, dict) else None
            if not isinstance(client, dict) or not client.get("id"):
                return {**base_res, "mode": "live", "http_status": 422, "response": response}
        order_args["client_id"] = client["id"]
    if order_args.get("client_id") and stype == "DELIVERY":
        address_id = entities.get("address_id")
        if isinstance(address_id, str) and _is_uuid(address_id):
            order_args["address_id"] = address_id
        else:
            args = {"client_id": order_args["client_id"], "address": entities["delivery_address"]}
            if entities.get("sub_premise_notes"):
                args["complement"] = entities["sub_premise_notes"]
            if coords.get("lat") is not None and coords.get("lng") is not None:
                args.update(latitude=coords["lat"], longitude=coords["lng"])
            ok_a, response = _mcp_call(mcp_url, api_key, "create_address", args)
            address = response.get("data") if ok_a and isinstance(response, dict) else None
            if not isinstance(address, dict) or not address.get("id"):
                return {**base_res, "mode": "live", "http_status": 422, "response": response}
            order_args["address_id"] = address["id"]

    ok, order_res = _mcp_call(mcp_url, api_key, "create_order", order_args)
    if not ok:
        return {**base_res, "mode": "live", "http_status": 422, "response": order_res}
    order_id = (order_res.get("data") or {}).get("id") if isinstance(order_res, dict) else None
    mcp_combos = [{k: v for k, v in c.items() if k != "product_name"} for c in resolved_combos if c.get("variant_id")]
    if order_id and mcp_combos:
        ok2, combo_res = _mcp_call(mcp_url, api_key, "add_order_combos", {"id": order_id, "combos": mcp_combos})
        if not ok2:
            return {**base_res, "mode": "live", "http_status": 422, "response": {"order": order_res, "combos": combo_res}}
        ok3, confirm_res = _mcp_call(mcp_url, api_key, "update_order_status", {"id": order_id, "status": "PENDING"})
        return {**base_res, "mode": "live", "http_status": 200 if ok3 else 422, "response": {"order": confirm_res if ok3 else order_res, "combos": combo_res}}
    return {**base_res, "mode": "live", "http_status": 502, "response": order_res}


def _run_order_modify_pipeline(
    action: str,
    entities: dict[str, Any],
    mcp_url: str,
    api_key: str,
    has_key: bool,
    allow_writes: bool,
    allow_destructive: bool,
    menu_body: Any,
    visible_cats: set[str] | None,
) -> dict[str, Any]:
    spec = ACTION_SPECS[action]
    tool_class = spec["class"]
    base_res: dict[str, Any] = {
        "action": action,
        "mcp_tool_class": tool_class,
        "required_scope": spec["scope"],
        "mcp_url": mcp_url,
        "method": "MCP",
        "endpoint": spec["mcp_tool"],
        "payload": entities,
    }
    if not has_key:
        return {**base_res, "mode": "dry_run", "dry_run_reason": "missing_api_key", "http_status": None, "response": None}

    status_ids = entities.get("order_ids")
    if action == "advance_order_status" and isinstance(status_ids, list) and status_ids:
        target = entities.get("new_status")
        actions = []
        resolved = set()
        for reference in status_ids:
            order, error, message = _resolve_order(mcp_url, api_key, {"order_id": reference})
            if error or order is None:
                return {**base_res, "mode": "validation", "clarification_reason": error, "suggested_message": message}
            if order["id"] in resolved:
                return {**base_res, "mode": "validation", "clarification_reason": "DUPLICATE_ORDER_REFERENCE"}
            current = str(order.get("status") or "").upper()
            if current not in STATUS_ORDER or target not in STATUS_ORDER or STATUS_ORDER.index(target) <= STATUS_ORDER.index(current):
                return {**base_res, "mode": "validation", "unsupported_reason": "BACKWARD_STATUS_NOT_ALLOWED"}
            resolved.add(order["id"])
            actions.append({"id": order["id"], "status": target})
        base_res["payload"] = actions
        if not allow_writes:
            return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None}
        results = []
        for args in actions:
            ok, response = _mcp_call(mcp_url, api_key, "update_order_status", args)
            results.append({"order_id": args["id"], "ok": ok, "response": response})
        return {**base_res, "mode": "live", "http_status": 200 if all(row["ok"] for row in results) else 422,
                "response": {"batch": results}}

    order, err_code, err_msg = _resolve_order(mcp_url, api_key, entities)
    if err_code:
        return {**base_res, "mode": "validation", "clarification_reason": err_code, "suggested_message": err_msg}
    assert order is not None
    oid = order["id"]
    cur_status = str(order.get("status") or "").upper()
    source = str(order.get("source") or "API").upper()

    if action in {"update_order", "cancel_order"} and cur_status in {"DELIVERED", "FINALIZED", "CANCELLED"}:
        return {**base_res, "mode": "validation", "unsupported_reason": "ORDER_ALREADY_CLOSED", "suggested_message": f"O pedido {order.get('public_id')} já está no estado '{cur_status}' e não pode ser alterado ou cancelado."}

    if action in {"update_order", "cancel_order", "apply_coupon_or_promo"} and source != "API":
        return {**base_res, "mode": "validation", "unsupported_reason": "NON_API_ORDER", "suggested_message": f"O pedido {order.get('public_id')} tem origem '{source}' e o MCP da OlaClick só permite alterar/cancelar pedidos criados via API."}

    can_execute = (tool_class == "write" and allow_writes) or (tool_class == "destructive" and allow_writes and allow_destructive)

    if action == "cancel_order":
        raw_reason = str(entities.get("reason") or "OTHER").strip()
        r_up = raw_reason.upper()
        c_args: dict[str, Any] = {"id": oid, "reason": r_up} if r_up in {"REJECTED_ORDER", "TEST_ORDER", "WRONG_ORDER", "FREE_ORDER", "DUPLICATED_ORDER", "OTHER"} else {"id": oid, "reason": "OTHER", "detail": raw_reason[:200]}
        base_res["payload"] = c_args
        if not can_execute:
            return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
        for pay in order.get("payments") or []:
            if isinstance(pay, dict) and not pay.get("canceled_at") and pay.get("id"):
                _mcp_call(mcp_url, api_key, "remove_order_payment", {"id": oid, "paymentId": str(pay["id"])})
        ok, res = _mcp_call(mcp_url, api_key, "cancel_order", c_args)
        return {**base_res, "mode": "live", "http_status": 200 if ok else 422, "response": res}

    if action == "advance_order_status":
        target = str(entities.get("new_status") or "").strip().upper()
        if target not in STATUS_ORDER[1:]:
            return {**base_res, "mode": "validation", "clarification_reason": "MISSING_NEW_STATUS", "suggested_message": "Indica um estado válido: PENDING, PREPARING, READY, DELIVERED ou FINALIZED."}
        if cur_status in STATUS_ORDER and STATUS_ORDER.index(target) <= STATUS_ORDER.index(cur_status):
            return {**base_res, "mode": "validation", "unsupported_reason": "BACKWARD_STATUS_NOT_ALLOWED", "suggested_message": f"O pedido já está em '{cur_status}'; na OlaClick os estados só avançam para a frente."}
        s_args = {"id": oid, "status": target}
        base_res["payload"] = s_args
        if not can_execute:
            return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
        ok, res = _mcp_call(mcp_url, api_key, "update_order_status", s_args)
        return {**base_res, "mode": "live", "http_status": 200 if ok else 422, "response": res}

    if action == "update_order":
        has_item_edits = any(entities.get(k) for k in ("items_add", "items_remove", "items_set_quantity", "items_swap"))
        if has_item_edits and cur_status not in {"INITIATED", "PENDING"}:
            return {**base_res, "mode": "validation", "unsupported_reason": "ORDER_ALREADY_IN_KITCHEN"}
        active = {c["id"]: c for c in (order.get("combos") or [])
                  if isinstance(c, dict) and c.get("id") and not c.get("canceled_at")}
        adds = list(entities.get("items_add") or [])
        removals = []
        combos = []
        touched = set()
        for field in ("items_swap", "items_remove", "items_set_quantity"):
            for change in entities.get(field) or []:
                cid = change.get("combo_id")
                if cid not in active or cid in touched:
                    return {**base_res, "mode": "validation", "clarification_reason": "ORDER_COMBO_ID_REQUIRED"}
                touched.add(cid)
                original = active[cid]
                current = original.get("quantity")
                qty = change.get("quantity")
                if type(current) is not int or current < 1:
                    return {**base_res, "mode": "live", "http_status": 502, "response": {"error": "ORDER_COMBO_QUANTITY_UNVERIFIED"}}
                if field == "items_swap":
                    adds.append(change.get("replacement"))
                    if qty is None:
                        qty = current
                if field in {"items_swap", "items_remove"}:
                    if qty is not None and (type(qty) is not int or not 1 <= qty <= current):
                        return {**base_res, "mode": "validation", "clarification_reason": "INVALID_QUANTITY"}
                    qty = current - qty if qty is not None else 0
                if type(qty) is not int or qty < 0:
                    return {**base_res, "mode": "validation", "clarification_reason": "INVALID_QUANTITY"}
                if qty < current:
                    removals.append(cid)
                count = qty - current if qty > current else qty if qty < current else 0
                if count:
                    vid = original.get("variant_id")
                    if not isinstance(vid, str) or not _is_uuid(vid):
                        return {**base_res, "mode": "live", "http_status": 502, "response": {"error": "ORDER_VARIANT_UNVERIFIED"}}
                    entry = {"variant_id": vid, "quantity": count, "modifiers": [
                        {"modifier_id": m["modifier_id"], "quantity": m.get("quantity", 1)}
                        for m in (original.get("modifiers") or []) if isinstance(m, dict) and m.get("modifier_id")
                    ]}
                    if original.get("comment"):
                        entry["comment"] = original["comment"]
                    combos.append(entry)

        if adds and (menu_body is None or visible_cats is None):
            return {**base_res, "mode": "live", "http_status": 502, "response": {"error": "CATALOG_UNAVAILABLE"}}
        if adds and entities.get("allergy_notes"):
            review = entities.get("allergy_review")
            if not isinstance(review, dict) or review.get("confirmed") is not True or not str(review.get("source") or "").strip():
                return {**base_res, "mode": "validation", "clarification_reason": "ALLERGY_REVIEW_REQUIRED"}
        catalog = {row["id"]: row for row in _catalog_items(menu_body, visible_cats)} if adds else {}
        for item in adds:
            if not isinstance(item, dict) or not isinstance(item.get("product_id"), str) or not _is_uuid(item["product_id"]):
                return {**base_res, "mode": "validation", "clarification_reason": "PRODUCT_ID_REQUIRED"}
            product = catalog.get(item["product_id"])
            if product is None:
                return {**base_res, "mode": "validation", "clarification_reason": "ITEM_NOT_FOUND"}
            entry, _, error = _combo_entry(mcp_url, api_key, product, item, catalog)
            if error:
                return {**base_res, "mode": "validation", "clarification_reason": error}
            combos.append({k: v for k, v in entry.items() if k != "product_name"})

        patch = {k: entities[k] for k in ("delivery_comment", "scheduled_delivery_date", "delivery_price", "packaging_price")
                 if entities.get(k) is not None}
        if entities.get("notes") is not None:
            patch["comment"] = entities["notes"]
        base_res["payload"] = {"order_id": oid, "patch": patch, "add": combos, "remove": removals}
        if not can_execute or (removals and not allow_destructive):
            return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None}
        step_results = {}
        if patch:
            ok, result = _mcp_call(mcp_url, api_key, "update_order", {"id": oid, **patch})
            step_results["update_order"] = result
            if not ok:
                return {**base_res, "mode": "live", "http_status": 422, "response": step_results}
        if combos:
            ok, result = _mcp_call(mcp_url, api_key, "add_order_combos", {"id": oid, "combos": combos})
            step_results["added"] = result
            if not ok:
                return {**base_res, "mode": "live", "http_status": 422, "response": step_results}
        for cid in removals:
            ok, result = _mcp_call(mcp_url, api_key, "remove_order_combo", {"id": oid, "comboId": cid})
            step_results.setdefault("removed", []).append(result)
            if not ok:
                return {**base_res, "mode": "live", "http_status": 422, "response": step_results}
        return {**base_res, "mode": "live", "http_status": 200, "response": step_results}

    if action == "apply_coupon_or_promo":
        if entities.get("remove_discount") or entities.get("discount_id"):
            discounts = order.get("discounts") or []
            did = entities.get("discount_id")
            if not did or not any(isinstance(discount, dict) and discount.get("id") == did for discount in discounts):
                return {**base_res, "mode": "validation", "clarification_reason": "NO_DISCOUNT_TO_REMOVE", "suggested_message": "Este pedido não tem descontos ativos para remover."}
            base_res["endpoint"] = "remove_order_discount"
            base_res["payload"] = {"id": oid, "discountId": did}
            if not (can_execute and allow_destructive):
                return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
            ok, res = _mcp_call(mcp_url, api_key, "remove_order_discount", {"id": oid, "discountId": str(did)})
            return {**base_res, "mode": "live", "http_status": 200 if ok else 422, "response": res}

        if entities.get("discount_type") and entities.get("discount_value") is not None and not entities.get("coupon_code"):
            d_args = {"id": oid, "type": str(entities["discount_type"]).upper(), "value": float(entities["discount_value"])}
            if entities.get("description"):
                d_args["description"] = str(entities["description"])[:100]
            base_res["endpoint"] = "add_order_discount"
            base_res["payload"] = d_args
            if not can_execute:
                return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
            ok, res = _mcp_call(mcp_url, api_key, "add_order_discount", d_args)
            return {**base_res, "mode": "live", "http_status": 200 if ok else 422, "response": res}

        if not order.get("client"):
            return {**base_res, "mode": "validation", "clarification_reason": "COUPON_REQUIRES_CLIENT", "suggested_message": "Na OlaClick, aplicar um cupão exige que o pedido tenha um cliente associado (nome e telefone)."}
        cp_args = {"id": oid, "code": str(entities.get("coupon_code") or "")}
        base_res["payload"] = cp_args
        if not can_execute:
            return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
        ok, res = _mcp_call(mcp_url, api_key, "apply_order_coupon", cp_args)
        if not ok:
            _, ap = _mcp_call(mcp_url, api_key, "get_active_promotions", {"timezone": "Europe/Lisbon"})
            return {**base_res, "mode": "live", "http_status": 422, "response": {"error": res, "active_promotions": ap}}
        return {**base_res, "mode": "live", "http_status": 200, "response": res}

    if action == "register_payment":
        if entities.get("remove_payment") or entities.get("payment_id"):
            pays = [p for p in (order.get("payments") or []) if isinstance(p, dict) and not p.get("canceled_at")]
            pay_id = entities.get("payment_id")
            if not pay_id or not any(payment.get("id") == pay_id for payment in pays):
                return {**base_res, "mode": "validation", "clarification_reason": "NO_PAYMENT_TO_REMOVE", "suggested_message": "Este pedido não tem pagamentos ativos para remover."}
            base_res["endpoint"] = "remove_order_payment"
            base_res["payload"] = {"id": oid, "paymentId": pay_id}
            if not (can_execute and allow_destructive):
                return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
            ok, res = _mcp_call(mcp_url, api_key, "remove_order_payment", {"id": oid, "paymentId": str(pay_id)})
            return {**base_res, "mode": "live", "http_status": 200 if ok else 422, "response": res}

        ok_pm, pm_res = _mcp_call(mcp_url, api_key, "list_payment_methods", {})
        methods = (pm_res.get("data") if isinstance(pm_res, dict) else []) if ok_pm else []
        if not ok_pm or not isinstance(methods, list):
            return {**base_res, "mode": "live", "http_status": 502, "response": pm_res}
        service = str(order.get("service_type") or "").upper()
        method_ids = {m["id"] for m in methods if isinstance(m, dict) and m.get("id")
                      and service in {str(value).upper() for value in (m.get("service_types") or [])}}
        pay_list = entities.get("payments") if isinstance(entities.get("payments"), list) and entities["payments"] else [entities]
        remaining = max(0.0, float(order.get("total") or 0) - float(order.get("total_paid") or 0))
        built_pays = []
        for p_item in pay_list:
            if not isinstance(p_item, dict):
                continue
            bill_amt = float(p_item["amount"]) if p_item.get("amount") is not None else remaining
            pm_id = p_item.get("payment_method_id")
            if not isinstance(pm_id, str) or pm_id not in method_ids:
                return {**base_res, "mode": "validation", "clarification_reason": "PAYMENT_METHOD_UNVERIFIED"}
            p_args: dict[str, Any] = {"id": oid, "payment_method_id": pm_id, "bill_amount": bill_amt}
            if p_item.get("received_amount") is not None:
                p_args["received_amount"] = float(p_item["received_amount"])
            if p_item.get("tip_amount") is not None:
                p_args["tip_amount"] = float(p_item["tip_amount"])
            built_pays.append(p_args)
        base_res["payload"] = built_pays[0] if len(built_pays) == 1 else built_pays
        if not can_execute:
            return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
        res_list = []
        for pa in built_pays:
            ok_p, res_p = _mcp_call(mcp_url, api_key, "add_order_payment", pa)
            res_list.append(res_p)
            if not ok_p:
                return {**base_res, "mode": "live", "http_status": 422, "response": res_list}
        return {**base_res, "mode": "live", "http_status": 200, "response": res_list[0] if len(res_list) == 1 else res_list}

    raise ValueError(f"Unhandled order_modify action: {action}")


def _menu_kitchen(mcp_url: str, api_key: str, kitchen_id: Any) -> str | None:
    ok, response = _mcp_call(mcp_url, api_key, "list_kitchens", {})
    rows = response.get("data") if ok and isinstance(response, dict) else None
    if not isinstance(rows, list):
        return None
    kitchens = [row for row in rows if isinstance(row, dict) and row.get("id")]
    if kitchen_id:
        chosen = [row["id"] for row in kitchens if row["id"] == kitchen_id]
    else:
        chosen = [row["id"] for row in kitchens if row.get("default") is True]
        if not chosen and len(kitchens) == 1:
            chosen = [kitchens[0]["id"]]
    return chosen[0] if len(chosen) == 1 else None


def _run_menu_manage_pipeline(
    action: str,
    entities: dict[str, Any],
    mcp_url: str,
    api_key: str,
    has_key: bool,
    allow_writes: bool,
    menu_body: Any,
    all_categories: list[dict[str, Any]],
    visible_cats: set[str] | None,
) -> dict[str, Any]:
    spec = ACTION_SPECS[action]
    base_res: dict[str, Any] = {
        "action": action,
        "mcp_tool_class": "write",
        "required_scope": spec["scope"],
        "mcp_url": mcp_url,
        "method": "MCP",
        "endpoint": spec["mcp_tool"],
        "payload": entities,
    }
    if not has_key:
        return {**base_res, "mode": "dry_run", "dry_run_reason": "missing_api_key", "http_status": None, "response": None}

    if action == "edit_menu" and isinstance(entities.get("categories"), list):
        if not allow_writes:
            return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
        kitchen_id = _menu_kitchen(mcp_url, api_key, entities.get("kitchen_id"))
        if not kitchen_id:
            return {**base_res, "mode": "validation", "clarification_reason": "KITCHEN_ID_REQUIRED"}
        existing_by_name = {_norm(c.get("name") or ""): c.get("id") for c in all_categories if isinstance(c, dict)}
        created_cats, reused_cats, created_prods, errors, tasks = 0, 0, 0, [], []
        for cat in entities["categories"]:
            if not isinstance(cat, dict):
                continue
            cname = str(cat.get("name") or "")
            cid = existing_by_name.get(_norm(cname))
            if cid:
                reused_cats += 1
            else:
                ok_c, cat_res = _mcp_call(mcp_url, api_key, "create_category", {"name": cname})
                cid = (cat_res.get("data") or {}).get("id") if isinstance(cat_res, dict) else None
                if ok_c and cid:
                    created_cats += 1
                    existing_by_name[_norm(cname)] = cid
                else:
                    errors.append({"category": cname, "error": cat_res})
                    continue
            for prod in cat.get("products") or []:
                if isinstance(prod, dict):
                    tasks.append((cid, prod))

        def _make_prod(t: tuple[str, dict[str, Any]]) -> tuple[bool, Any, str]:
            cid, p = t
            price = float(p.get("price") or 0)
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
                    "variants": [{"name": "Default", "price": price, "original_price": price, "sku": uuid.uuid4().hex[:12]}],
                },
            )
            return ok_p, res_p, str(p.get("name"))

        with ThreadPoolExecutor(max_workers=6) as pool:
            for ok_p, res_p, pname in pool.map(_make_prod, tasks):
                if ok_p:
                    created_prods += 1
                else:
                    errors.append({"product": pname, "error": res_p})
        return {
            **base_res,
            "mode": "live",
            "http_status": 200 if not errors else 422,
            "response": {"created_categories": created_cats, "reused_categories": reused_cats, "created_products": created_prods, "errors": errors[:20]},
        }

    if action == "edit_menu" and entities.get("operation") == "create_product":
        cname = str(entities.get("category_id") or entities.get("category_query") or "")
        matched = [c for c in all_categories if isinstance(c, dict) and _norm(cname) in {_norm(c.get("id")), _norm(c.get("name"))}]
        if not matched:
            return {**base_res, "mode": "validation", "clarification_reason": "CATEGORY_NOT_FOUND", "suggested_message": f"Categoria '{cname}' não encontrada."}
        if len(matched) > 1:
            return {**base_res, "mode": "validation", "clarification_reason": "AMBIGUOUS_CATEGORY", "candidates": matched}
        cid = matched[0]["id"]
        pname = str(entities.get("name") or "").strip()
        if menu_body and _search_menu_matches(menu_body, pname, visible_category_ids={str(matched[0].get("id"))}):
            ex = [m for m in _search_menu_matches(menu_body, pname) if _norm(m["name"]) == _norm(pname)]
            if ex:
                return {**base_res, "mode": "validation", "clarification_reason": "DUPLICATE_PRODUCT", "suggested_message": f"Já existe um produto chamado '{pname}' nessa categoria."}
        if not allow_writes:
            return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
        kid = _menu_kitchen(mcp_url, api_key, entities.get("kitchen_id"))
        if not kid:
            return {**base_res, "mode": "validation", "clarification_reason": "KITCHEN_ID_REQUIRED"}
        p_val = float(entities.get("price") or 0)
        op_val = float(entities.get("original_price") or p_val)
        c_args = {"category_id": cid, "kitchen_id": kid, "name": pname[:191], "description": str(entities.get("description") or ""), "visible": True, "variants": [{"name": "Default", "price": p_val, "original_price": max(p_val, op_val), "sku": str(entities.get("sku") or uuid.uuid4().hex[:12])[:20]}]}
        ok, res = _mcp_call(mcp_url, api_key, "create_product", c_args)
        return {**base_res, "endpoint": "create_product", "payload": c_args, "mode": "live", "http_status": 200 if ok else 422, "response": res}

    if action == "edit_menu" and entities.get("operation") == "create_variant":
        q = str(entities.get("product_id") or entities.get("product_query") or "")
        prod, err, _ = _resolve_single_product(menu_body, q, visible_cats)
        if err or not prod:
            return {**base_res, "mode": "validation", "clarification_reason": err or "ITEM_NOT_FOUND", "suggested_message": f"Produto '{q}' não encontrado ou ambíguo."}
        p_val = float(entities.get("price") or 0)
        op_val = float(entities.get("original_price") or p_val)
        cv_args = {"id": prod["id"], "name": str(entities.get("name") or "Variante"), "price": p_val, "original_price": max(p_val, op_val), "sku": str(entities.get("sku") or uuid.uuid4().hex[:12])[:20]}
        if not allow_writes:
            return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
        ok, res = _mcp_call(mcp_url, api_key, "create_product_variant", cv_args)
        return {**base_res, "endpoint": "create_product_variant", "payload": cv_args, "mode": "live", "http_status": 200 if ok else 422, "response": res}

    if action == "edit_menu" and (entities.get("category_query") or entities.get("category_id")):
        patch = entities.get("patch") if isinstance(entities.get("patch"), dict) else {}
        cid = entities.get("category_id")
        cat_obj = None
        if not cid:
            cq = _norm(entities.get("category_query") or "")
            matched = [c for c in all_categories if isinstance(c, dict) and cq == _norm(c.get("name"))]
            if not matched:
                return {**base_res, "mode": "validation", "clarification_reason": "CATEGORY_NOT_FOUND", "suggested_message": f"Categoria '{entities.get('category_query')}' não encontrada."}
            if len(matched) > 1:
                opts = ", ".join(str(c.get("name")) for c in matched)
                return {**base_res, "mode": "validation", "clarification_reason": "AMBIGUOUS_CATEGORY", "suggested_message": f"Várias categorias correspondem ({opts}). Qual delas queres editar?"}
            cat_obj = matched[0]
            cid = cat_obj.get("id")
        if entities.get("operation") == "delete_category":
            ok_lp, lp = _mcp_call(mcp_url, api_key, "list_products", {"category_id": cid, "per_page": 1})
            has_prods = bool((lp.get("data") if isinstance(lp, dict) else []) if ok_lp else [])
            if has_prods:
                return {**base_res, "mode": "validation", "unsupported_reason": "CATEGORY_NOT_EMPTY", "suggested_message": "A categoria ainda tem produtos ativos. Esconde a categoria (`visible: false`) ou move os produtos antes de apagar."}
            if not allow_writes:
                return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
            ok_d, res_d = _mcp_call(mcp_url, api_key, "delete_category", {"categoryId": cid})
            return {**base_res, "endpoint": "delete_category", "mode": "live", "http_status": 200 if ok_d else 422, "response": res_d}
        if "price_delta" in patch or "price_percent" in patch:
            cat_prods = _catalog_items(menu_body, category=str(cid))
            if not allow_writes:
                return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "payload": {"products_count": len(cat_prods), "patch": patch}, "http_status": None, "response": None}
            updated = 0
            for cp in cat_prods:
                old_p = float(cp.get("price") or 0)
                new_p = round(old_p + float(patch["price_delta"]), 2) if "price_delta" in patch else round(old_p * (1 + float(patch["price_percent"]) / 100.0), 2)
                if new_p >= 0 and cp.get("variant_id"):
                    ok_u, _ = _mcp_call(mcp_url, api_key, "update_product_variant", {"id": cp["id"], "variantId": cp["variant_id"], "price": new_p, "original_price": max(old_p, new_p)})
                    if ok_u:
                        updated += 1
            return {**base_res, "endpoint": "update_product_variant(bulk)", "mode": "live", "http_status": 200, "response": {"updated_products": updated}}
        if cat_obj and str(cat_obj.get("type") or "").upper() == "FAVORITE" and "position" in patch:
            return {**base_res, "mode": "validation", "unsupported_reason": "FAVORITE_CATEGORY_IMMUTABLE", "suggested_message": "A categoria de destaques (`FAVORITE`) não pode ser reposicionada."}
        u_args = {"id": cid, **{k: patch[k] for k in ("visible", "position") if k in patch}}
        base_res["endpoint"] = "update_category"
        base_res["payload"] = u_args
        if not allow_writes:
            return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
        ok, res = _mcp_call(mcp_url, api_key, "update_category", u_args)
        return {**base_res, "mode": "live", "http_status": 200 if ok else 422, "response": res}

    if entities.get("apply_all"):
        return {**base_res, "mode": "validation", "clarification_reason": "PRODUCT_IDS_REQUIRED"}
    pid = entities.get("product_id")
    if not isinstance(pid, str) or not _is_uuid(pid):
        return {**base_res, "mode": "validation", "clarification_reason": "PRODUCT_ID_REQUIRED"}
    ok_p, p_full_res = _mcp_call(mcp_url, api_key, "get_product", {"id": pid})
    p_full = p_full_res.get("data") if ok_p and isinstance(p_full_res, dict) else None
    if not isinstance(p_full, dict) or p_full.get("id") != pid:
        return {**base_res, "mode": "live", "http_status": 502, "response": p_full_res}
    patch = entities.get("patch") if isinstance(entities.get("patch"), dict) else {}
    variant_change = action in {"set_item_out_of_stock", "restore_item_in_stock"} or any(
        key in patch for key in ("price", "original_price", "stock", "stock_threshold", "packaging_price", "end_promo")
    )
    vid = entities.get("variant_id")
    cur_orig_price = 0
    if variant_change:
        variants = [v for v in p_full.get("variants") or [] if isinstance(v, dict) and v.get("id")]
        selected = [v for v in variants if v["id"] == vid] if vid else variants
        if len(selected) != 1:
            return {**base_res, "mode": "validation",
                    "clarification_reason": "INVALID_VARIANT" if vid else "AMBIGUOUS_VARIANT",
                    "candidates": variants}
        vid = selected[0]["id"]
        cur_orig_price = float(selected[0].get("original_price") or 0)

    if action in {"set_item_out_of_stock", "restore_item_in_stock"}:
        stock_val = 0 if action == "set_item_out_of_stock" else entities.get("stock")
        if type(stock_val) is not int or stock_val < (0 if action == "set_item_out_of_stock" else 1):
            return {**base_res, "mode": "validation", "clarification_reason": "INVALID_MENU_PATCH", "suggested_message": "O stock não pode ser negativo."}
        if isinstance(p_full, dict) and p_full.get("stock_enabled") is False:
            return {
                **base_res,
                "mode": "validation",
                "unsupported_reason": "STOCK_TRACKING_DISABLED_ON_PRODUCT",
                "suggested_message": (
                    f"O produto '{p_full.get('name')}' está com controlo de stock desativado (`stock_enabled: false`) na OlaClick, "
                    "e o servidor MCP oficial não expõe o toggle `stock_enabled` nem `visible` por produto. "
                    "Ativa o controlo de stock uma vez no painel da OlaClick para este produto, ou esconde a categoria inteira."
                ),
            }
        v_args = {"id": pid, "variantId": vid, "stock": stock_val}
        base_res["endpoint"] = "update_product_variant"
        base_res["payload"] = v_args
        if not allow_writes:
            return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
        ok, res = _mcp_call(mcp_url, api_key, "update_product_variant", v_args)
        return {**base_res, "mode": "live", "http_status": 200 if ok else 422, "response": res}

    patch = entities.get("patch") if isinstance(entities.get("patch"), dict) else {}
    if "visible" in patch or "available" in patch:
        return {
            **base_res,
            "mode": "validation",
            "unsupported_reason": "PRODUCT_VISIBILITY_NOT_IN_MCP",
            "suggested_message": "O servidor MCP oficial da OlaClick (`update_product`) apenas permite editar `name` e `description` de um produto (a visibilidade só pode ser alterada ao nível da categoria via `update_category`).",
        }
    if any(k in patch and float(patch[k]) < 0 for k in ("price", "original_price", "stock", "packaging_price") if patch.get(k) is not None):
        return {**base_res, "mode": "validation", "clarification_reason": "INVALID_MENU_PATCH", "suggested_message": "Preços e stock não podem ser negativos."}
    if "price" in patch and "original_price" in patch and float(patch["price"]) > float(patch["original_price"]):
        return {**base_res, "mode": "validation", "clarification_reason": "INVALID_MENU_PATCH", "suggested_message": "`price` não pode ser maior que `original_price`."}

    if not allow_writes:
        return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}

    out_steps: dict[str, Any] = {}
    if any(k in patch for k in ("name", "description")):
        p_args = {"product_id": pid, **{k: patch[k] for k in ("name", "description") if k in patch}}
        ok1, r1 = _mcp_call(mcp_url, api_key, "update_product", p_args)
        out_steps["update_product"] = r1
        if not ok1:
            return {**base_res, "mode": "live", "http_status": 422, "response": out_steps}
    if any(k in patch for k in ("price", "original_price", "stock", "stock_threshold", "packaging_price", "end_promo")):
        v_args = {"id": pid, "variantId": vid}
        if patch.get("end_promo"):
            v_args["price"] = cur_orig_price
        elif "price" in patch:
            new_p = float(patch["price"])
            v_args["price"] = new_p
            v_args["original_price"] = float(patch["original_price"]) if "original_price" in patch else max(new_p, cur_orig_price)
        elif "original_price" in patch:
            v_args["original_price"] = float(patch["original_price"])
        for k in ("stock", "stock_threshold", "packaging_price"):
            if k in patch:
                v_args[k] = patch[k]
        ok2, r2 = _mcp_call(mcp_url, api_key, "update_product_variant", v_args)
        out_steps["update_product_variant"] = r2
        if not ok2:
            return {**base_res, "mode": "live", "http_status": 422, "response": out_steps}
    if "position" in patch:
        ok3, r3 = _mcp_call(mcp_url, api_key, "update_product_position", {"id": pid, "position": int(patch["position"])})
        out_steps["update_product_position"] = r3
        if not ok3:
            return {**base_res, "mode": "live", "http_status": 422, "response": out_steps}
    return {**base_res, "mode": "live", "http_status": 200, "response": out_steps}


def _run_logistics_pipeline(
    action: str,
    entities: dict[str, Any],
    mcp_url: str,
    api_key: str,
    has_key: bool,
    allow_writes: bool,
) -> dict[str, Any]:
    spec = ACTION_SPECS[action]
    base_res: dict[str, Any] = {
        "action": action,
        "mcp_tool_class": spec["class"],
        "required_scope": spec["scope"],
        "mcp_url": mcp_url,
        "method": "MCP",
        "endpoint": spec["mcp_tool"],
        "payload": entities,
    }
    if not has_key:
        return {**base_res, "mode": "dry_run", "dry_run_reason": "missing_api_key", "http_status": None, "response": None}

    if action == "quote_delivery":
        ok_p, pricing = _mcp_call(mcp_url, api_key, "get_delivery_pricing", {})
        resp: dict[str, Any] = {"pricing_rules": pricing}
        coords = entities.get("coordinates") if isinstance(entities.get("coordinates"), dict) else {}
        q_args: dict[str, Any] = {}
        if coords.get("lat") is not None and coords.get("lng") is not None:
            q_args = {"latitude": float(coords["lat"]), "longitude": float(coords["lng"])}
        elif entities.get("district_id"):
            q_args = {"district_id": str(entities["district_id"])}
        if q_args:
            ok_q, quote = _mcp_call(mcp_url, api_key, "get_delivery_quote", q_args)
            resp["quote"] = quote
            q_data = quote.get("data") if (ok_q and isinstance(quote, dict)) else None
            if isinstance(q_data, dict) and q_data.get("price") == 0 and q_data.get("area") is None:
                resp["out_of_coverage"] = True
                resp["coverage_warning"] = "Morada fora da área padrão de entrega (4 km). O valor 0 € na resposta significa fora de cobertura (sujeito a confirmação/taxa da loja), NÃO entrega grátis."
        return {**base_res, "mode": "live", "http_status": 200 if ok_p else 422, "response": resp}

    order, err_code, err_msg = _resolve_order(mcp_url, api_key, entities)
    if err_code:
        return {**base_res, "mode": "validation", "clarification_reason": err_code, "suggested_message": err_msg}
    assert order is not None
    oid = order["id"]
    if str(order.get("service_type") or "").upper() != "DELIVERY":
        return {**base_res, "mode": "validation", "unsupported_reason": "NOT_A_DELIVERY_ORDER", "suggested_message": f"O pedido {order.get('public_id')} é do tipo {order.get('service_type')}, não DELIVERY."}
    if str(order.get("status") or "").upper() in {"CANCELLED", "FINALIZED"}:
        return {**base_res, "mode": "validation", "unsupported_reason": "ORDER_ALREADY_CLOSED", "suggested_message": f"O pedido {order.get('public_id')} já está '{order.get('status')}'."}

    if action == "assign_rider":
        if entities.get("unassign"):
            base_res["endpoint"] = "unassign_rider"
            base_res["payload"] = {"id": oid}
            if not allow_writes:
                return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
            ok, res = _mcp_call(mcp_url, api_key, "unassign_rider", {"id": oid})
            return {**base_res, "mode": "live", "http_status": 200 if ok else 422, "response": res}
        provider = str(entities.get("provider") or "api").lower()
        if provider == "olaclick" and (not entities.get("rider_id") or str(order.get("status") or "").upper() == "PENDING"):
            return {**base_res, "mode": "validation", "unsupported_reason": "OLACLICK_RIDER_REQUIRES_PREPARING_AND_USER_ID", "suggested_message": "Com provider 'olaclick' é obrigatório `rider_id` e o pedido não pode estar em PENDING."}
        rider_name = entities.get("rider_name")
        if not isinstance(rider_name, str) or not rider_name.strip():
            return {**base_res, "mode": "validation", "clarification_reason": "RIDER_NAME_REQUIRED"}
        r_args: dict[str, Any] = {"id": oid, "name": rider_name, "provider": provider}
        if entities.get("rider_phone"):
            r_args["phone_number"] = str(entities["rider_phone"])
        if entities.get("rider_id"):
            r_args["user_id"] = str(entities["rider_id"])
        base_res["endpoint"] = "assign_rider"
        base_res["payload"] = r_args
        if not allow_writes:
            return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
        ok, res = _mcp_call(mcp_url, api_key, "assign_rider", r_args)
        return {**base_res, "mode": "live", "http_status": 200 if ok else 422, "response": res}

    if action == "update_delivery_status":
        d_status = str(entities.get("delivery_status") or "").strip().upper()
        if d_status in {"DELIVERING", "ARRIVED_AT_DELIVERY", "DELIVERED"} and not order.get("rider"):
            return {**base_res, "mode": "validation", "clarification_reason": "NO_RIDER_ASSIGNED", "suggested_message": f"O pedido {order.get('public_id')} ainda não tem estafeta atribuído antes de passar para '{d_status}'."}
        if str(order.get("delivery_status") or "").upper() == "DELIVERED" and d_status != "DELIVERED":
            return {**base_res, "mode": "validation", "unsupported_reason": "DELIVERY_ALREADY_COMPLETED", "suggested_message": f"A entrega do pedido {order.get('public_id')} já está marcada como DELIVERED."}
        d_args = {"id": oid, "delivery_status": d_status}
        base_res["payload"] = d_args
        if not allow_writes:
            return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
        ok, res = _mcp_call(mcp_url, api_key, "update_delivery_status", d_args)
        return {**base_res, "mode": "live", "http_status": 200 if ok else 422, "response": res}

    if action == "report_rider_position":
        rider = order.get("rider") if isinstance(order.get("rider"), dict) else None
        if not rider or not rider.get("name"):
            return {**base_res, "mode": "validation", "clarification_reason": "NO_RIDER_ASSIGNED", "suggested_message": f"O pedido {order.get('public_id')} ainda não tem estafeta atribuído."}
        lat = float(entities["latitude"])
        lng = float(entities["longitude"])
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return {**base_res, "mode": "validation", "clarification_reason": "INVALID_COORDINATES", "suggested_message": "Coordenadas GPS inválidas."}
        pos_args = {"id": oid, "name": rider["name"], "latitude": lat, "longitude": lng}
        base_res["payload"] = pos_args
        if not allow_writes:
            return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
        ok, res = _mcp_call(mcp_url, api_key, "report_rider_position", pos_args)
        return {**base_res, "mode": "live", "http_status": 200 if ok else 422, "response": res}

    raise ValueError(f"Unhandled logistics action: {action}")


def _run_one(
    op: dict[str, Any],
    actor: str,
    mcp_url: str,
    api_key: str,
    has_key: bool,
    allow_writes: bool,
    allow_destructive: bool,
    cached_menu: tuple[bool, Any] | None,
    all_categories: list[dict[str, Any]],
    visible_cats: set[str] | None,
    company_data: dict[str, Any] | None,
) -> dict[str, Any]:
    action = op["intent"]
    entities = op.get("entities") or {}
    menu_body = cached_menu[1] if (cached_menu and cached_menu[0]) else None

    if action == "unsupported_request":
        reason = str(entities.get("reason") or entities.get("requested_action") or "Esta operação não é suportada pelo sistema.")
        return {
            "action": action,
            "mcp_tool_class": "read",
            "required_scope": "none",
            "mcp_url": mcp_url,
            "method": "MCP",
            "endpoint": "none",
            "payload": entities,
            "mode": "validation",
            "unsupported_reason": "UNSUPPORTED_CAPABILITY",
            "suggested_message": f"Operação não suportada: {reason}",
        }

    is_promo_write = action == "manage_promotions" and str(entities.get("operation") or "create").lower() not in {"list", "get"}
    if actor == "customer" and (action in OWNER_ONLY_INTENTS or is_promo_write):
        return {
            "action": action,
            "mcp_tool_class": "read",
            "required_scope": "none",
            "mcp_url": mcp_url,
            "method": "MCP",
            "endpoint": "none",
            "payload": entities,
            "mode": "validation",
            "unsupported_reason": "UNAUTHORIZED_ACTOR",
            "suggested_message": "Esta operação é exclusiva do gerente/dono do restaurante.",
        }

    if action == "create_order":
        return _run_create_order_pipeline(entities, mcp_url, api_key, has_key, allow_writes, menu_body, visible_cats, company_data)

    if action in {"update_order", "cancel_order", "advance_order_status", "apply_coupon_or_promo", "register_payment"}:
        return _run_order_modify_pipeline(action, entities, mcp_url, api_key, has_key, allow_writes, allow_destructive, menu_body, visible_cats)

    if action in {"quote_delivery", "assign_rider", "update_delivery_status", "report_rider_position"}:
        return _run_logistics_pipeline(action, entities, mcp_url, api_key, has_key, allow_writes)

    if action in {"set_item_out_of_stock", "restore_item_in_stock", "edit_menu"}:
        return _run_menu_manage_pipeline(action, entities, mcp_url, api_key, has_key, allow_writes, menu_body, all_categories, visible_cats)

    spec = ACTION_SPECS[action]
    today = datetime.now(ZoneInfo("Europe/Lisbon")).strftime("%Y-%m-%d")
    base_res: dict[str, Any] = {
        "action": action,
        "mcp_tool_class": spec["class"],
        "required_scope": spec["scope"],
        "mcp_url": mcp_url,
        "method": "MCP",
        "endpoint": spec["mcp_tool"],
        "payload": entities,
    }
    if not has_key:
        return {**base_res, "mode": "dry_run", "dry_run_reason": "missing_api_key", "http_status": None, "response": None}

    if action in {"check_menu_item", "get_menu_category"}:
        if menu_body is None or visible_cats is None:
            return {**base_res, "mode": "live", "http_status": 502, "response": {"error": "CATALOG_UNAVAILABLE"}}
        if action == "check_menu_item":
            target = str(entities.get("product_id") or entities.get("product_query") or "")
            matches = _search_menu_matches(menu_body, target, visible_category_ids=visible_cats)
            details = None
            if entities.get("include_details") is True and len(matches) == 1:
                ok, details = _mcp_call(mcp_url, api_key, "get_product", {"id": matches[0]["id"]})
                if not ok:
                    return {**base_res, "mode": "live", "http_status": 422, "response": details}
            return {**base_res, "mode": "live", "http_status": 200, "menu_matches": matches, "response": details}

        if any(entities.get(field) for field in ("dietary", "include_ingredient", "exclude_ingredient")):
            return {**base_res, "mode": "validation", "clarification_reason": "CATALOG_SELECTION_REQUIRED"}
        category = str(entities.get("category_id") or entities.get("category_query") or "")
        fields = ("max_price", "min_price", "cheapest", "only_unavailable", "include_details")
        if not category and not any(entities.get(k) is not None for k in fields):
            return {**base_res, "mode": "live", "http_status": 200,
                    "menu_summary": _summarize_available_menu(menu_body, visible_cats), "response": None}
        products = _catalog_items(menu_body, visible_cats, category)
        if entities.get("include_details") is not True or entities.get("only_unavailable") is not None:
            products = [p for p in products if p["available"] != bool(entities.get("only_unavailable"))]
        minimum, maximum = entities.get("min_price"), entities.get("max_price")
        if minimum is not None or maximum is not None:
            products = [p for p in products if any(
                isinstance(v.get("price"), (int, float)) and
                (minimum is None or v["price"] >= minimum) and (maximum is None or v["price"] <= maximum)
                for v in p["variants"] if isinstance(v, dict)
            )]
        if entities.get("cheapest"):
            products.sort(key=lambda p: min((v["price"] for v in p["variants"] if isinstance(v, dict)
                                             and isinstance(v.get("price"), (int, float))), default=float("inf")))
        return {**base_res, "mode": "live", "http_status": 200, "menu_matches": products, "response": None}

    if action == "check_store_hours_or_open":
        ok, comp = _mcp_call(mcp_url, api_key, "get_company", {})
        resp: dict[str, Any] = {"company": comp}
        if entities.get("check_external_apps"):
            _, apps = _mcp_call(mcp_url, api_key, "get_store_status", {})
            resp["external_apps"] = apps
        return {**base_res, "mode": "live", "http_status": 200 if ok else 422, "response": resp}

    if action == "check_order_status":
        order, err_code, err_msg = _resolve_order(mcp_url, api_key, entities)
        if err_code:
            return {**base_res, "mode": "validation", "clarification_reason": err_code, "suggested_message": err_msg}
        return {**base_res, "mode": "live", "http_status": 200, "response": order}

    if action == "list_active_orders":
        s_date = str(entities.get("start_date") or today)
        e_date = str(entities.get("end_date") or today)
        if s_date > e_date:
            return {**base_res, "mode": "validation", "clarification_reason": "INVALID_DATE_RANGE", "suggested_message": "`start_date` não pode ser posterior a `end_date`."}
        args: dict[str, Any] = {"start_date": s_date, "end_date": e_date, "timezone": "Europe/Lisbon"}
        for field in ("status", "cancelation_reason"):
            if entities.get(field):
                args[field] = entities[field]
        if entities.get("service_type"):
            args["service_types"] = entities["service_type"]
        if entities.get("payment_status"):
            args["payment_status"] = str(entities["payment_status"]).upper()
        ok, res = _mcp_call(mcp_url, api_key, "get_orders", args)
        return {**base_res, "payload": args, "mode": "live", "http_status": 200 if ok else 422, "response": res}

    if action == "sales_summary":
        s_date = str(entities.get("start_date") or today)
        e_date = str(entities.get("end_date") or today)
        if s_date > e_date:
            return {**base_res, "mode": "validation", "clarification_reason": "INVALID_DATE_RANGE", "suggested_message": "`start_date` não pode ser posterior a `end_date`."}
        rtype = str(entities.get("report_type") or "summary").lower()
        if rtype == "cashier":
            ok_c, cashiers = _mcp_call(mcp_url, api_key, "list_cashiers", {})
            _, balances = _mcp_call(mcp_url, api_key, "list_cashier_balances", {"start_date": s_date, "end_date": e_date, "timezone": "Europe/Lisbon"})
            out = {"cashiers": cashiers, "balances": balances}
            return {**base_res, "endpoint": "list_cashiers+list_cashier_balances", "mode": "live", "http_status": 200 if ok_c else 422, "sales_summary": out, "response": out}
        if rtype in {"tables", "users", "webhooks"}:
            tmap = {"tables": "list_tables", "users": "list_users", "webhooks": "list_webhooks"}
            ok_x, res_x = _mcp_call(mcp_url, api_key, tmap[rtype], {})
            return {**base_res, "endpoint": tmap[rtype], "mode": "live", "http_status": 200 if ok_x else 422, "sales_summary": {rtype: res_x}, "response": res_x}
        report_tools = {
            "summary": ("get_orders_summary", {"start_date": s_date, "end_date": e_date, "sources": ALL_SOURCES, "timezone": "Europe/Lisbon"}),
            "by_hour": ("get_sales_by_hour", {"start_date": s_date, "end_date": e_date, "sources": ALL_SOURCES, "timezone": "Europe/Lisbon"}),
            "by_day": ("get_sales_by_day", {"start_date": s_date, "end_date": e_date, "sources": ALL_SOURCES, "timezone": "Europe/Lisbon"}),
            "by_service_type": ("get_orders_by_service_type", {"start_date": s_date, "end_date": e_date, "sources": ALL_SOURCES, "timezone": "Europe/Lisbon"}),
            "by_source": ("get_orders_by_source", {"start_date": s_date, "end_date": e_date, "sources": ALL_SOURCES, "timezone": "Europe/Lisbon"}),
            "top_payments": ("get_top_payment_methods", {"start_date": s_date, "end_date": e_date, "sources": ALL_SOURCES, "timezone": "Europe/Lisbon"}),
            "margins": ("get_margins_summary", {"start_date": s_date, "end_date": e_date, "timezone": "Europe/Lisbon"}),
            "product_margins": ("get_product_margins", {"start_date": s_date, "end_date": e_date, "timezone": "Europe/Lisbon"}),
            "menu_conversion": ("get_menu_conversion", {"start_date": s_date, "end_date": e_date, "timezone": "Europe/Lisbon"}),
        }
        if rtype not in report_tools:
            return {**base_res, "mode": "validation", "clarification_reason": "REPORT_TYPE_REQUIRED"}
        tool_name, args = report_tools[rtype]
        ok, summary_res = _mcp_call(mcp_url, api_key, tool_name, args)
        sales_out: dict[str, Any] = {rtype: summary_res}
        if entities.get("include_top_products"):
            _, top_res = _mcp_call(mcp_url, api_key, "get_products_sold", {"start_date": s_date, "end_date": e_date, "show_products": int(entities.get("top_limit") or 5), "timezone": "Europe/Lisbon"})
            sales_out["top_products"] = top_res
        return {**base_res, "endpoint": tool_name, "payload": args, "mode": "live", "http_status": 200 if ok else 422, "sales_summary": sales_out, "response": sales_out}

    if action == "manage_promotions":
        op_type = str(entities.get("operation") or "create").lower()
        if op_type == "list":
            base_res["mcp_tool_class"] = "read"
            base_res["endpoint"] = "get_active_promotions"
            ap_args: dict[str, Any] = {"timezone": "Europe/Lisbon"}
            if entities.get("service_type_filter"):
                ap_args["service_type"] = str(entities["service_type_filter"]).lower()
            if entities.get("redeemable_now") is not None:
                ap_args["redeemable_now"] = bool(entities["redeemable_now"])
            ok, res = _mcp_call(mcp_url, api_key, "get_active_promotions", ap_args)
            return {**base_res, "payload": ap_args, "mode": "live", "http_status": 200 if ok else 422, "response": res}
        pid = entities.get("promotion_id")
        if op_type in {"get", "update", "delete"} and (not isinstance(pid, str) or not _is_uuid(pid)):
            return {**base_res, "mode": "validation", "clarification_reason": "PROMOTION_ID_REQUIRED"}
        if op_type in {"get", "delete"}:
            tool = f"{op_type}_promotion"
            base_res.update(endpoint=tool, payload={"id": pid},
                            mcp_tool_class="read" if op_type == "get" else "destructive")
            if op_type == "delete" and not (allow_writes and allow_destructive):
                return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None}
            ok, res = _mcp_call(mcp_url, api_key, tool, {"id": pid})
            return {**base_res, "mode": "live", "http_status": 200 if ok else 422, "response": res}
        if op_type not in {"create", "update"}:
            return {**base_res, "mode": "validation", "clarification_reason": "PROMOTION_OPERATION_REQUIRED"}

        fields = ("name", "discount_type", "discount_value", "minimum_order_amount", "valid_from", "valid_until",
                  "usage_limit", "published", "promotion_type", "service_types", "audience",
                  "usage_limit_per_customer", "schedule", "terms")
        params = {key: entities[key] for key in fields if entities.get(key) is not None}
        if entities.get("code"):
            params["coupon_code"] = entities["code"]
        if op_type == "create":
            required = {"name", "coupon_code", "discount_type", "discount_value", "minimum_order_amount",
                        "valid_from", "valid_until", "published"}
            if not required.issubset(params) or "usage_limit" not in entities:
                return {**base_res, "mode": "validation", "clarification_reason": "MISSING_PROMOTION_DETAILS"}
            params["usage_limit"] = entities["usage_limit"]

        if entities.get("product_queries"):
            return {**base_res, "mode": "validation", "clarification_reason": "PRODUCT_IDS_REQUIRED"}
        if entities.get("promotion_type") == "products" or entities.get("products") is not None:
            products = entities.get("products")
            if not isinstance(products, list) or not products or params.get("promotion_type") != "products":
                return {**base_res, "mode": "validation", "clarification_reason": "PRODUCT_IDS_REQUIRED"}
            if menu_body is None or visible_cats is None:
                return {**base_res, "mode": "live", "http_status": 502, "response": {"error": "CATALOG_UNAVAILABLE"}}
            catalog = {row["id"]: row["name"] for row in _catalog_items(menu_body, visible_cats)}
            picks = []
            for product in products:
                if not isinstance(product, dict) or catalog.get(str(product.get("id"))) != product.get("name") or not product.get("name"):
                    return {**base_res, "mode": "validation", "clarification_reason": "INVALID_PROMOTION_PRODUCT"}
                picks.append({"id": product["id"], "name": product["name"]})
            if len({pick["id"] for pick in picks}) != len(picks):
                return {**base_res, "mode": "validation", "clarification_reason": "INVALID_PROMOTION_PRODUCT"}
            params["products"] = picks

        if op_type == "update":
            if not params:
                return {**base_res, "mode": "validation", "clarification_reason": "MISSING_PROMOTION_CHANGES"}
            params["id"] = pid
        tool = f"{op_type}_promotion"
        base_res.update(endpoint=tool, payload=params)
        if not allow_writes:
            return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None}
        ok, res = _mcp_call(mcp_url, api_key, tool, params)
        return {**base_res, "mode": "live", "http_status": 200 if ok else 422, "response": res}

    if action == "manage_customer_address":
        if str(entities.get("operation") or "upsert").lower() == "lookup":
            base_res["mcp_tool_class"] = "read"
            base_res["endpoint"] = "get_clients"
            phone_l = re.sub(r"\D+", "", str(entities.get("customer_phone") or ""))
            lk_args: dict[str, Any] = {"include_addresses": True}
            if phone_l:
                lk_args["filter_phone_number"] = phone_l
            elif entities.get("customer_name"):
                lk_args["filter_name"] = str(entities["customer_name"])
            ok_l, res_l = _mcp_call(mcp_url, api_key, "get_clients", lk_args)
            return {**base_res, "payload": lk_args, "mode": "live", "http_status": 200 if ok_l else 422, "response": res_l}
        if not allow_writes:
            return {**base_res, "mode": "dry_run", "dry_run_reason": "safety_gate_disabled", "http_status": None, "response": None}
        cid = entities.get("customer_id")
        out_client: dict[str, Any] = {}
        if not cid:
            ok_c, client = _lookup_exact_client(mcp_url, api_key, entities)
            if not ok_c:
                return {**base_res, "mode": "live", "http_status": 422, "response": client}
            if client is None:
                if not entities.get("customer_name"):
                    return {**base_res, "mode": "validation", "clarification_reason": "CUSTOMER_NAME_REQUIRED"}
                args = {"name": entities["customer_name"], "phone_number": entities["customer_phone"],
                        "country_calling_code": entities["country_calling_code"]}
                if entities.get("email"):
                    args["email"] = entities["email"]
                ok_c, response = _mcp_call(mcp_url, api_key, "create_client", args)
                out_client["client"] = response
                client = response.get("data") if ok_c and isinstance(response, dict) else None
                if not isinstance(client, dict) or not client.get("id"):
                    return {**base_res, "mode": "live", "http_status": 422, "response": out_client}
            cid = client["id"]
        if cid and entities.get("delivery_address"):
            addr_args: dict[str, Any] = {"client_id": cid, "address": str(entities["delivery_address"])[:191]}
            for k in ("complement", "reference"):
                if entities.get(k):
                    addr_args[k] = str(entities[k])[:100]
            coords = entities.get("coordinates") if isinstance(entities.get("coordinates"), dict) else {}
            if coords.get("lat") is not None and coords.get("lng") is not None:
                addr_args["latitude"] = float(coords["lat"])
                addr_args["longitude"] = float(coords["lng"])
            ok_a, a_res = _mcp_call(mcp_url, api_key, "create_address", addr_args)
            out_client["address"] = a_res
            return {**base_res, "mode": "live", "http_status": 200 if ok_a else 422, "response": out_client}
        return {**base_res, "mode": "live", "http_status": 200, "response": out_client}

    raise ValueError(f"Unsupported action: {action}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute or dry-run OlaClick official MCP pipeline(s).")
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
    actor = str(stage01.get("actor") or "unknown")
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
        op["intent"] in {"check_menu_item", "get_menu_category", "create_order", "update_order", "set_item_out_of_stock", "restore_item_in_stock", "edit_menu"}
        or (op["intent"] == "manage_promotions" and bool((op.get("entities") or {}).get("products")))
        for op in operations
    )
    needs_company = any(op["intent"] == "create_order" for op in operations)
    cached_menu: tuple[bool, Any] | None = None
    all_categories: list[dict[str, Any]] = []
    visible_cats: set[str] | None = None
    company_data: dict[str, Any] | None = None

    if has_key and (needs_menu or needs_company):
        with ThreadPoolExecutor(max_workers=3) as pre_pool:
            f_menu = pre_pool.submit(_mcp_call, mcp_url, api_key, "get_menu", {}) if needs_menu else None
            f_cats = pre_pool.submit(_mcp_call, mcp_url, api_key, "list_categories", {}) if needs_menu else None
            f_comp = pre_pool.submit(_mcp_call, mcp_url, api_key, "get_company", {}) if needs_company else None
            if f_menu and f_cats:
                cached_menu = f_menu.result()
                ok_c, cats_body = f_cats.result()
                if ok_c and isinstance(cats_body, dict) and isinstance(cats_body.get("data"), list):
                    all_categories = [c for c in cats_body["data"] if isinstance(c, dict)]
                    visible_cats = {str(c.get("id") or "") for c in all_categories if c.get("visible") is True}
            if f_comp:
                ok_co, co_body = f_comp.result()
                if ok_co and isinstance(co_body, dict) and isinstance(co_body.get("data"), dict):
                    company_data = co_body["data"]

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(operations)))) as pool:
        results = list(
            pool.map(
                lambda op: _run_one(op, actor, mcp_url, api_key, has_key, allow_writes, allow_destructive, cached_menu, all_categories, visible_cats, company_data),
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
