from typing import Any

from app.core.database import execute, query_one, to_json
from app.core.exceptions import BusinessError


def audit(action: str, entity_type: str, entity_id: int | None, actor_id: int | None, detail: dict | None = None) -> None:
    execute(
        "INSERT INTO audit_logs(actor_user_id, action, entity_type, entity_id, detail_json) VALUES (?, ?, ?, ?, ?)",
        (actor_id, action, entity_type, entity_id, to_json(detail or {})),
    )


def row_or_404(sql: str, params: tuple[Any, ...], code: str, message: str) -> dict[str, Any]:
    row = query_one(sql, params)
    if not row:
        raise BusinessError(code, message, 404)
    return row


def paginate(items: list[dict[str, Any]], page: int = 1, page_size: int = 20) -> dict[str, Any]:
    start = (page - 1) * page_size
    return {"items": items[start : start + page_size], "page": page, "page_size": page_size, "total": len(items)}
