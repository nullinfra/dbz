#!/usr/bin/env python3
"""Stage 02 finalizer: deterministic pipeline policy evaluation for single or multi-op runs."""
import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_run_dir(run_id: str | None, out_dir: str | None) -> Path:
    if out_dir:
        return Path(out_dir)
    if not run_id:
        active = Path(tempfile.gettempdir()) / "olaclick-icm" / ".active-run"
        if not active.is_file():
            raise RuntimeError("No active run found. Run Stage 01 write_stage01.py --start first.")
        run_id = active.read_text(encoding="utf-8").strip()
    return _repo_root() / "output" / "runs" / run_id


ENTITY_CHECKS: dict[str, list[tuple[Any, str, str]]] = {
    "create_order": [
        (
            lambda e: not (isinstance(e.get("ambiguous_notes"), list) and len(e["ambiguous_notes"]) > 0),
            "AMBIGUOUS_ITEM_NOTE",
            "Nota ou restrição ambígua (ex.: 'sem queijo' quando há vários itens). Perguntar ao cliente a qual item se aplica.",
        ),
        (
            lambda e: not (isinstance(e.get("ambiguous_quantities"), list) and len(e["ambiguous_quantities"]) > 0),
            "AMBIGUOUS_QUANTITY",
            "Quantidade ambígua distribuída por vários sabores. Perguntar exatamente quantas unidades de cada sabor deseja.",
        ),
        (lambda e: bool(e.get("repeat_last_order")) or (isinstance(e.get("items"), list) and len(e["items"]) > 0), "MISSING_ORDER_ITEMS", "Pedido sem itens. Perguntar ao cliente quais produtos e quantidades deseja."),
        (
            lambda e: all(isinstance(i, dict) and type(i.get("quantity")) is int and i["quantity"] >= 1 for i in (e.get("items") or [])),
            "INVALID_QUANTITY",
            "Quantidade inválida num dos itens. Perguntar um número inteiro positivo de unidades.",
        ),
    ],
    "update_order": [
        (
            lambda e: not (isinstance(e.get("ambiguous_notes"), list) and len(e["ambiguous_notes"]) > 0),
            "AMBIGUOUS_ITEM_NOTE",
            "Nota ambígua na alteração do pedido. Perguntar a qual item se refere.",
        ),
        (
            lambda e: any(e.get(k) is not None for k in ("items_add", "items_remove", "items_set_quantity", "items_swap", "delivery_price", "packaging_price", "new_status", "notes", "delivery_comment", "scheduled_delivery_date")),
            "MISSING_ORDER_CHANGES",
            "Não foi indicado o que alterar no pedido. Perguntar qual a alteração pretendida.",
        ),
    ],
    "check_menu_item": [
        (lambda e: bool(e.get("product_id") or e.get("product_query")), "MISSING_PRODUCT_QUERY", "Falta o produto a verificar no menu."),
    ],
    "cancel_order": [],
    "set_item_out_of_stock": [
        (lambda e: bool(e.get("product_query") or e.get("product_id")), "MISSING_PRODUCT_QUERY", "Falta indicar qual o produto a marcar como esgotado."),
    ],
    "restore_item_in_stock": [
        (lambda e: bool(e.get("product_query") or e.get("product_id")), "MISSING_PRODUCT_QUERY", "Falta indicar qual o produto a repor em stock."),
    ],
    "edit_menu": [
        (
            lambda e: (isinstance(e.get("categories"), list) and len(e["categories"]) > 0)
            or (str(e.get("operation") or "") in {"create_product", "create_variant", "delete_category"})
            or (bool(e.get("product_query") or e.get("product_id") or e.get("category_query") or e.get("category_id")) and isinstance(e.get("patch"), dict) and len(e["patch"]) > 0),
            "MISSING_MENU_EDIT_DETAILS",
            "Falta indicar o produto/categoria e alterações (`patch`) ou a lista `categories` para editar o menu.",
        ),
    ],
    "check_order_status": [],
    "quote_delivery": [
        (lambda e: bool(e.get("delivery_address") or e.get("coordinates") or e.get("district_id")), "MISSING_DELIVERY_ADDRESS", "Falta a morada ou coordenadas para cotar a entrega."),
    ],
    "apply_coupon_or_promo": [
        (lambda e: bool(e.get("remove_discount") or e.get("discount_id") or e.get("coupon_code") or (e.get("discount_type") and e.get("discount_value") is not None)), "MISSING_COUPON_CODE", "Falta indicar o código do cupão ou o valor do desconto."),
    ],
    "get_menu_category": [],
    "manage_customer_address": [
        (lambda e: any(e.get(k) for k in ("delivery_address", "customer_phone", "customer_name", "customer_id")), "MISSING_CUSTOMER_DETAILS", "Falta indicar morada, telefone ou nome do cliente."),
    ],
    "advance_order_status": [
        (lambda e: bool(e.get("new_status")), "MISSING_NEW_STATUS", "Falta indicar o novo estado do pedido (PENDING, PREPARING, READY, DELIVERED ou FINALIZED)."),
    ],
    "assign_rider": [
        (lambda e: bool(e.get("unassign") or e.get("rider_id") or e.get("rider_name")), "MISSING_RIDER", "Falta indicar o nome ou ID do estafeta."),
    ],
    "update_delivery_status": [
        (lambda e: bool(e.get("delivery_status")), "MISSING_DELIVERY_STATUS", "Falta indicar o novo estado de entrega (ex.: DELIVERING, ARRIVED_AT_DELIVERY, DELIVERED)."),
    ],
    "report_rider_position": [
        (lambda e: e.get("latitude") is not None and e.get("longitude") is not None, "MISSING_COORDINATES", "Faltam as coordenadas GPS (`latitude` e `longitude`) do estafeta."),
    ],
    "register_payment": [
        (lambda e: bool(e.get("remove_payment") or e.get("payment_method_id") or (isinstance(e.get("payments"), list) and len(e["payments"]) > 0)), "MISSING_PAYMENT_METHOD", "Falta indicar o método de pagamento."),
    ],
    "manage_promotions": [
        (lambda e: str(e.get("operation") or "create").lower() not in {"get", "update", "delete"} or bool(e.get("promotion_id")), "MISSING_PROMOTION_ID", "Falta o ID da promoção."),
        (
            lambda e: str(e.get("operation") or "create").lower() != "create" or (bool(e.get("code")) and (e.get("discount_value") is not None or e.get("discount_percent") is not None or e.get("discount_amount") is not None)),
            "MISSING_PROMOTION_DETAILS",
            "Para criar uma promoção é obrigatório indicar o código (`code`) e o valor do desconto (`discount_value`).",
        ),
    ],
}

STATUS_PRIORITY = {
    "API_ERROR": 6,
    "UNSUPPORTED_OPERATION": 5,
    "NEEDS_CLARIFICATION": 4,
    "NEEDS_CONFIRMATION": 3,
    "PLANNED_DRY_RUN": 2,
    "COMPLETED": 1,
    "NO_ACTION": 0,
}


def _check_required_entities(intent: str, entities: dict[str, Any]) -> tuple[str | None, str | None]:
    for predicate, code, msg in ENTITY_CHECKS.get(intent, []):
        if not predicate(entities):
            return code, msg
    return None, None


def _evaluate_operation(op: dict[str, Any], mcp_data: dict[str, Any] | None) -> dict[str, Any]:
    intent = op["intent"]
    pipeline = op.get("pipeline") or "unknown"
    entities = op.get("entities") or {}

    if intent == "unsupported_request":
        reason = str(entities.get("reason") or entities.get("requested_action") or "Esta funcionalidade não é suportada pelo MCP da OlaClick.")
        return {
            "intent": intent,
            "pipeline": pipeline,
            "entities": entities,
            "status": "UNSUPPORTED_OPERATION",
            "clarification_reason": None,
            "unsupported_reason": "UNSUPPORTED_CAPABILITY",
            "needs_clarification": False,
            "confirmation_required": False,
            "proposed_action": None,
            "mcp_result": None,
            "suggested_message": f"Esta operação não é possível no sistema: {reason}",
        }

    # If olaclick_mcp.py caught a pre-flight validation/ambiguity/unsupported constraint, surface it first!
    if mcp_data and mcp_data.get("mode") == "validation":
        if mcp_data.get("unsupported_reason"):
            return {
                "intent": intent,
                "pipeline": pipeline,
                "entities": entities,
                "status": "UNSUPPORTED_OPERATION",
                "clarification_reason": None,
                "unsupported_reason": mcp_data["unsupported_reason"],
                "needs_clarification": False,
                "confirmation_required": False,
                "proposed_action": None,
                "mcp_result": {"candidates": mcp_data.get("candidates")} if mcp_data.get("candidates") else None,
                "suggested_message": mcp_data.get("suggested_message"),
            }
        if mcp_data.get("clarification_reason"):
            return {
                "intent": intent,
                "pipeline": pipeline,
                "entities": entities,
                "status": "NEEDS_CLARIFICATION",
                "clarification_reason": mcp_data["clarification_reason"],
                "unsupported_reason": None,
                "needs_clarification": True,
                "confirmation_required": False,
                "proposed_action": None,
                "mcp_result": {"candidates": mcp_data.get("candidates")} if mcp_data.get("candidates") else None,
                "suggested_message": mcp_data.get("suggested_message"),
            }

    clar_reason, clar_msg = _check_required_entities(intent, entities)
    if clar_reason:
        return {
            "intent": intent,
            "pipeline": pipeline,
            "entities": entities,
            "status": "NEEDS_CLARIFICATION",
            "clarification_reason": clar_reason,
            "unsupported_reason": None,
            "needs_clarification": True,
            "confirmation_required": False,
            "proposed_action": None,
            "mcp_result": None,
            "suggested_message": clar_msg,
        }

    if not mcp_data:
        raise RuntimeError(f"Missing MCP result for actionable intent '{intent}'")

    mode = mcp_data.get("mode")
    http_status = mcp_data.get("http_status")
    tool_class = mcp_data.get("mcp_tool_class")

    if mode == "dry_run":
        if tool_class in {"write", "destructive"}:
            status = "NEEDS_CONFIRMATION"
            confirm_req = True
            msg = f"Ação '{intent}' ({mcp_data.get('method')} {mcp_data.get('endpoint')}) preparada em dry-run ({mcp_data.get('dry_run_reason')}). Confirmar antes de executar."
        else:
            status = "PLANNED_DRY_RUN"
            confirm_req = False
            msg = f"Leitura '{intent}' preparada em dry-run (falta OLACLICK_API_KEY em ola_click/.env)."
    elif isinstance(http_status, int) and 200 <= http_status < 300:
        status = "COMPLETED"
        confirm_req = False
        msg = None
    else:
        status = "API_ERROR"
        confirm_req = False
        msg = f"Erro na chamada OlaClick em '{intent}' (HTTP {http_status})."

    return {
        "intent": intent,
        "pipeline": pipeline,
        "entities": entities,
        "status": status,
        "clarification_reason": None,
        "unsupported_reason": None,
        "needs_clarification": False,
        "confirmation_required": confirm_req,
        "proposed_action": {
            "method": mcp_data.get("method"),
            "endpoint": mcp_data.get("endpoint"),
            "required_scope": mcp_data.get("required_scope"),
            "payload": mcp_data.get("payload"),
        },
        "mcp_result": {
            "mode": mode,
            "http_status": http_status,
            "menu_matches": mcp_data.get("menu_matches"),
            "menu_summary": mcp_data.get("menu_summary"),
            "sales_summary": mcp_data.get("sales_summary"),
            "response": mcp_data.get("response"),
        },
        "suggested_message": msg,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Stage 02 and write orientation.json.")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    run_dir = _resolve_run_dir(args.run_id, args.out_dir)
    intent_path = run_dir / "stage01_intent.json"
    if not intent_path.is_file():
        print(f"ERROR: Missing {intent_path}", file=sys.stderr)
        return 1

    stage01 = json.loads(intent_path.read_text(encoding="utf-8"))
    operations = stage01.get("operations") or [{"intent": stage01["intent"], "pipeline": stage01.get("pipeline"), "entities": stage01.get("entities") or {}}]

    if not stage01.get("is_olaclick_action"):
        orientation: dict[str, Any] = {
            "run_id": stage01["run_id"],
            "raw_text": stage01["raw_text"],
            "is_olaclick_action": False,
            "actor": stage01["actor"],
            "intent": "non_actionable",
            "pipeline": "gate",
            "active_pipelines": [],
            "status": "NO_ACTION",
            "needs_clarification": False,
            "confirmation_required": False,
            "operations_count": 0,
            "results": [],
            "proposed_action": None,
            "mcp_result": None,
            "suggested_message": None,
        }
        (run_dir / "orientation.json").write_text(json.dumps(orientation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(orientation, indent=2, ensure_ascii=False))
        return 0

    mcp_path = run_dir / "mcp_raw_output.json"
    mcp_raw = json.loads(mcp_path.read_text(encoding="utf-8")) if mcp_path.is_file() else {}
    mcp_results = mcp_raw.get("results") or ([mcp_raw] if mcp_raw else [])

    eval_results: list[dict[str, Any]] = []
    for idx, op in enumerate(operations):
        m_item = mcp_results[idx] if idx < len(mcp_results) else None
        try:
            eval_results.append(_evaluate_operation(op, m_item))
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    overall_status = max((r["status"] for r in eval_results), key=lambda s: STATUS_PRIORITY.get(s, -1))
    messages = [r["suggested_message"] for r in eval_results if r.get("suggested_message")]

    orientation = {
        "run_id": stage01["run_id"],
        "raw_text": stage01["raw_text"],
        "is_olaclick_action": True,
        "actor": stage01["actor"],
        "intent": stage01["intent"],
        "pipeline": stage01.get("pipeline"),
        "active_pipelines": stage01.get("active_pipelines") or [],
        "entities": stage01.get("entities") or {},
        "status": overall_status,
        "clarification_reason": eval_results[0].get("clarification_reason") if len(eval_results) == 1 else None,
        "unsupported_reason": eval_results[0].get("unsupported_reason") if len(eval_results) == 1 else None,
        "needs_clarification": any(r["needs_clarification"] for r in eval_results),
        "confirmation_required": any(r["confirmation_required"] for r in eval_results),
        "operations_count": len(eval_results),
        "results": eval_results,
        "proposed_action": eval_results[0]["proposed_action"] if len(eval_results) == 1 else None,
        "mcp_result": eval_results[0]["mcp_result"] if len(eval_results) == 1 else None,
        "suggested_message": " | ".join(messages) if messages else None,
    }

    (run_dir / "orientation.json").write_text(json.dumps(orientation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(orientation, indent=2, ensure_ascii=False))
    return 0 if overall_status != "API_ERROR" else 1


if __name__ == "__main__":
    raise SystemExit(main())
