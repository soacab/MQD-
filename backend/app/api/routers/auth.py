from typing import Any

from fastapi import APIRouter, Body, Depends

from app.api.deps import current_user
from app.api.responses import ok
from app.services import auth_service

router = APIRouter()


@router.post("/api/v1/auth/login")
def login(payload: dict = Body(...)) -> dict[str, Any]:
    return ok(auth_service.login(payload))


@router.get("/api/v1/auth/iam/login-url")
def iam_login_url(state: str | None = None) -> dict[str, Any]:
    return ok(auth_service.iam_login_url(state))


@router.get("/api/v1/auth/iam/callback")
def iam_callback(code: str | None = None, state: str | None = None) -> dict[str, Any]:
    return ok(auth_service.iam_callback(code, state))


@router.get("/api/v1/auth/me")
def me(user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(auth_service.serialize_user(user))


@router.get("/api/v1/users")
def list_users(
    keyword: str | None = None,
    status: str | None = None,
    permission: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(current_user),
) -> dict[str, Any]:
    return ok(auth_service.list_users(keyword, status, permission, page, page_size, user))


@router.get("/api/v1/business-user-options")
def list_business_user_options(user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(auth_service.list_business_user_options(user))


@router.post("/api/v1/users")
def create_user(payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(auth_service.create_user(payload, user))


@router.put("/api/v1/users/{user_id}")
def update_user(user_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(auth_service.update_user(user_id, payload, user))


@router.put("/api/v1/users/{user_id}/permissions")
def update_user_permissions(user_id: int, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(auth_service.update_user_permissions(user_id, payload, user))


@router.post("/api/v1/users/{user_id}/disable")
def disable_user(user_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(auth_service.disable_user(user_id, user))


@router.post("/api/v1/users/{user_id}/enable")
def enable_user(user_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(auth_service.enable_user(user_id, user))


@router.delete("/api/v1/users/{user_id}")
def delete_user(user_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(auth_service.delete_user(user_id, user))


@router.get("/api/v1/system-settings")
def get_system_settings(_: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(auth_service.get_system_settings())


@router.put("/api/v1/system-settings/{key}")
def save_system_setting(key: str, payload: dict = Body(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(auth_service.save_system_setting(key, payload, user))


@router.get("/api/v1/audit-logs")
def list_audit_logs(user: dict = Depends(current_user)) -> dict[str, Any]:
    return ok(auth_service.list_audit_logs(user))
