from fastapi import APIRouter, Depends, Response, status
from supabase import AsyncClient

from app.api.onboarding import schemas, views
from app.core import dependencies as deps
from app.services import onboarding
from app.core.config import load_settings

load_settings()

onboarding_router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


@onboarding_router.post(
    "/organization",
    response_model=views.Organization,
    status_code=status.HTTP_201_CREATED,
)
async def onboard_organization(
    resp: Response,
    organization: schemas.OnboardOrganization,
    db: AsyncClient = Depends(deps.get_db),
) -> dict:
    onboarding_service = onboarding.OnboardingService(db)
    response = await onboarding_service.onboard_organization(organization)

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

    return response["organization"]


@onboarding_router.post(
    "/resource", 
    response_model=views.Resource, 
    status_code=status.HTTP_201_CREATED,
)
async def onboard_resource(
    resp: Response,
    resource: schemas.OnboardResource,
    db: AsyncClient = Depends(deps.get_db),
)-> dict:
    onboarding_service = onboarding.OnboardingService(db)
    response = await onboarding_service.onboard_resource(resource)

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

    return response["resource"]
    
