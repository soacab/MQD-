from typing import Any


def ok(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return {"success": True, "data": data if data is not None else {}, "message": message}
