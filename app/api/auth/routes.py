from fastapi import APIRouter, Depends, Response, Request, status
from supabase import AsyncClient
from redis.asyncio import Redis

from app.api.auth import schemas
from app.api.onboarding import views
from app.core import exceptions, dependencies as deps
from app.services import auth
from app.core.config import load_settings

load_settings()

auth_router = APIRouter(prefix="/api/auth", tags=["Auth"])


@auth_router.post(
    "/login", 
    response_model=views.User,
)
async def login_user(
    resp: Response,
    credentials: schemas.LoginUser,
    db: AsyncClient = Depends(deps.get_db),
    _: None = Depends(deps.rate_limit_login),
) -> dict:
    auth_service = auth.AuthService(db)
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

    return response["user"]

@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_user(
    req: Request,
    resp: Response,
    db: AsyncClient = Depends(deps.get_db),
    cache: Redis = Depends(deps.get_cache),
):
    if not req.cookies or not req.cookies.get("access_token") or not req.cookies.get("refresh_token"):
        raise exceptions.AuthorizationError(detail="Please make sure you are logged in")

    auth_service = auth.AuthService(db, cache)
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

@auth_router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
async def refresh(
    req: Request,
    resp: Response,
    db: AsyncClient = Depends(deps.get_db),
    cache: Redis = Depends(deps.get_cache),
):
    if not req.cookies or not req.cookies.get("access_token") or not req.cookies.get("refresh_token"):
        raise exceptions.AuthorizationError(detail="Please make sure you are logged in")

    auth_service = auth.AuthService(db, cache)

    response =  await auth_service.refresh(
        req.cookies["refresh_token"],
        req.cookies["access_token"],
    )

    resp.set_cookie(
        "refresh_token",
        response["fresh_access_token"],
        httponly=True,
        secure=True if load_settings().is_production else False,
        samesite="lax",
    )
    
@auth_router.get("/me", response_model=views.User)
async def get_me(
    user: dict = Depends(deps.get_current_user),
)-> dict:
    return user
