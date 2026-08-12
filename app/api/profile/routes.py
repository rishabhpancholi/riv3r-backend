from fastapi import APIRouter, Depends
from supabase import AsyncClient

from app.api.profile import schemas
from app.api.onboarding import views
from app.core import dependencies as deps
from app.services import profile

profile_router = APIRouter(prefix="/api/profile", tags=["Profile"])


@profile_router.patch(
    "/organization/{organization_id}",
    response_model=views.Organization,
)
async def update_organization(
    organization_id: str,
    organization: schemas.UpdateOrganization,
    user: dict = Depends(deps.get_current_user),
    db: AsyncClient = Depends(deps.get_db),
) -> dict:
    profile_service = profile.ProfileService(db)
    return await profile_service.update_organization(organization_id, organization, user)


@profile_router.patch(
    "/user",
    response_model=views.User,
)
async def update_user(
    user_updates: schemas.UpdateUser,
    user: dict = Depends(deps.get_current_user),
    db: AsyncClient = Depends(deps.get_db),
) -> dict:
    profile_service = profile.ProfileService(db)
    return await profile_service.update_user(user_updates, user)


@profile_router.patch(
    "/resource/{user_id}",
    response_model=views.Resource,
)
async def update_resource(
    user_id: str,
    resource: schemas.UpdateResource,
    user: dict = Depends(deps.get_current_user),
    db: AsyncClient = Depends(deps.get_db),
) -> dict:
    profile_service = profile.ProfileService(db)
    return await profile_service.update_resource(user_id, resource, user)
