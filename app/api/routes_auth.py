from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.dependencies import get_container
from app.api.responses import api_response
from app.core.auth import (
    clear_session_cookie,
    create_session_token,
    session_from_request,
    set_session_cookie,
    validate_credentials,
)
from app.core.container import ServiceContainer
from app.core.exceptions import AuthenticationError
from app.domain.schemas import LoginRequest


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/session")
def auth_session(
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    auth_settings = container.settings.auth
    if not auth_settings.enabled:
        return api_response(
            success=True,
            message="Authentication is disabled.",
            data={"enabled": False, "authenticated": True, "username": None},
        )

    session = session_from_request(request, auth_settings)
    return api_response(
        success=True,
        message="Loaded auth session successfully.",
        data={
            "enabled": True,
            "authenticated": session is not None,
            "username": session.username if session else None,
        },
    )


@router.post("/login")
def login(
    payload: LoginRequest,
    container: ServiceContainer = Depends(get_container),
) -> JSONResponse:
    auth_settings = container.settings.auth
    if not auth_settings.enabled:
        return JSONResponse(
            content=api_response(
                success=True,
                message="Authentication is disabled.",
                data={"enabled": False, "authenticated": True, "username": None},
            )
        )

    if not validate_credentials(auth_settings, payload.username, payload.password):
        raise AuthenticationError("账号或密码错误。")

    token = create_session_token(auth_settings, payload.username)
    response = JSONResponse(
        content=api_response(
            success=True,
            message="登录成功。",
            data={"enabled": True, "authenticated": True, "username": payload.username},
        )
    )
    set_session_cookie(response, auth_settings, token)
    return response


@router.post("/logout")
def logout(container: ServiceContainer = Depends(get_container)) -> JSONResponse:
    response = JSONResponse(
        content=api_response(
            success=True,
            message="已退出登录。",
            data={"enabled": container.settings.auth.enabled, "authenticated": False, "username": None},
        )
    )
    clear_session_cookie(response, container.settings.auth)
    return response
