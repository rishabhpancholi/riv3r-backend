from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import load_settings
from app.core.exception_handlers import register_exception_handlers
from app.db.connection import Connection
from app.api.onboarding.routes import onboarding_router
from app.api.auth.routes import auth_router
from app.api.profile.routes import profile_router
from app.middlewares import middlewares

settings = load_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    connection = Connection(settings)
    await connection.init_db()
    connection.init_cache()
    app.state.connection = connection

    yield

    await connection.close_cache()


app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    description="Where work flows seamlessly",
    openapi_url="/openapi.json" if not settings.is_production else None,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

register_exception_handlers(app)

routers = [onboarding_router, auth_router, profile_router]
for router in routers:
    app.include_router(router)

middlewares: list[BaseHTTPMiddleware] = [CORSMiddleware, middlewares.RequestIDMiddleware, middlewares.RequestTimeMiddleware]
for middleware in middlewares:
    app.add_middleware(middleware)


@app.get("/api/health", tags=["Health"])
def health() -> dict:
    return {
        "status": "healthy",
        "name": settings.app_name,
        "version": settings.app_version,
    }
