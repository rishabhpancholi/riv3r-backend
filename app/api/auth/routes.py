from fastapi import APIRouter, Depends, Request, Response, status

from app.api.auth import schemas
from app.api.onboarding import views
from app.api.auth import dependencies as deps
from app.core import dependencies as core_deps
from app.core import exceptions
from app.core.config import load_settings
from app.services.auth import AuthService
from app.services.audit import AuditService
from app.utils import jwt

load_settings()

auth_router = APIRouter(prefix="/api/auth", tags=["Auth"])


@auth_router.post(
    "/login",
    response_model=views.User,
)
async def login_user(
    req: Request,
    resp: Response,
    credentials: schemas.LoginUser,
    auth_service: AuthService = Depends(deps.get_auth_service),
    audit_service: AuditService = Depends(core_deps.get_audit_service),
    _: None = Depends(deps.rate_limit_login),
) -> dict:
    response = await auth_service.login_user(credentials)

    resp.set_cookie(
        "access_token",
        response["access_token"],
        httponly=True,
        secure=True if load_settings().is_production else False,
        samesite="lax",
    )
    resp.set_cookie(
        "refresh_token",
        response["refresh_token"],
        httponly=True,
        secure=True if load_settings().is_production else False,
        samesite="lax",
    )

    await audit_service.log(
        req,
        user_id=response["user"]["id"],
        entity_type="user",
        task_type="login",
    )

    return response["user"]


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_user(
    req: Request,
    resp: Response,
    auth_service: AuthService = Depends(deps.get_auth_service),
    audit_service: AuditService = Depends(core_deps.get_audit_service),
):
    if (
        not req.cookies
        or not req.cookies.get("access_token")
        or not req.cookies.get("refresh_token")
    ):
        raise exceptions.AuthorizationError(detail="Please make sure you are logged in")

    await auth_service.logout_user(
        req.cookies["access_token"],
        req.cookies["refresh_token"],
    )

    resp.delete_cookie(
        "access_token",
        httponly=True,
        secure=True if load_settings().is_production else False,
        samesite="lax",
    )
    resp.delete_cookie(
        "refresh_token",
        httponly=True,
        secure=True if load_settings().is_production else False,
        samesite="lax",
    )

    user_id = None
    try:
        user_id = jwt.decode_token(
            req.cookies["access_token"], expected_type="access", allow_expired=True
        )["id"]
    except Exception:
        pass

    await audit_service.log(
        req,
        user_id=user_id,
        entity_type="user",
        task_type="logout",
    )


@auth_router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
async def refresh(
    req: Request,
    resp: Response,
    auth_service: AuthService = Depends(deps.get_auth_service),
    audit_service: AuditService = Depends(core_deps.get_audit_service),
):
    if (
        not req.cookies
        or not req.cookies.get("access_token")
        or not req.cookies.get("refresh_token")
    ):
        raise exceptions.AuthorizationError(detail="Please make sure you are logged in")

    response = await auth_service.refresh(
        req.cookies["refresh_token"],
        req.cookies["access_token"],
    )

    resp.set_cookie(
        "access_token",
        response["fresh_access_token"],
        httponly=True,
        secure=True if load_settings().is_production else False,
        samesite="lax",
    )

    user_id = None
    try:
        user_id = jwt.decode_token(
            req.cookies["refresh_token"], expected_type="refresh"
        )["id"]
    except Exception:
        pass

    await audit_service.log(
        req,
        user_id=user_id,
        entity_type="user",
        task_type="refresh",
    )


@auth_router.get("/me", response_model=views.User)
async def get_me(
    user: dict = Depends(core_deps.get_current_user),
) -> dict:
    return user
