from fastapi import APIRouter, Depends, Request, Response, status

from app.api.onboarding import schemas, views
from app.core import dependencies as deps
from app.core.config import load_settings
from app.services.onboarding import OnboardingService
from app.services.audit import AuditService

load_settings()

onboarding_router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


@onboarding_router.post(
    "/organization",
    response_model=views.Organization,
    status_code=status.HTTP_201_CREATED,
)
async def onboard_organization(
    req: Request,
    resp: Response,
    organization: schemas.OnboardOrganization,
    onboarding_service: OnboardingService = Depends(
        deps.get_onboarding_service
    ),
    audit_service: AuditService = Depends(deps.get_audit_service),
    _: None = Depends(deps.rate_limit_onboarding),
) -> dict:
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

    await audit_service.log(
        req,
        user_id=response["organization"]["owner"]["id"],
        entity_type="organization",
        task_type="organization_onboard",
    )

    return response["organization"]


@onboarding_router.post(
    "/resource",
    response_model=views.Resource,
    status_code=status.HTTP_201_CREATED,
)
async def onboard_resource(
    req: Request,
    resp: Response,
    resource: schemas.OnboardResource,
    onboarding_service: OnboardingService = Depends(
        deps.get_onboarding_service
    ),
    audit_service: AuditService = Depends(deps.get_audit_service),
    _: None = Depends(deps.rate_limit_onboarding),
) -> dict:
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

    await audit_service.log(
        req,
        user_id=response["resource"]["id"],
        entity_type="resource",
        task_type="resource_onboard",
    )

    return response["resource"]
