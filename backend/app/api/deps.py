from typing import Any

import jwt
from fastapi import Header

from app.core.config import settings
from app.core.database import query_one
from app.core.enums import UserStatus
from app.core.exceptions import BusinessError


def current_user(authorization: str = Header(default="")) -> dict[str, Any]:
    if not authorization.startswith("Bearer "):
        raise BusinessError("UNAUTHORIZED", "缺少认证信息", 401)
    try:
        payload = jwt.decode(
            authorization.removeprefix("Bearer "),
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise BusinessError("UNAUTHORIZED", "认证信息无效", 401) from exc
    user = query_one("SELECT * FROM users WHERE id = ? AND status = ?", (user_id, UserStatus.ACTIVE))
    if not user:
        raise BusinessError("UNAUTHORIZED", "用户不存在或已停用", 401)
    return user
