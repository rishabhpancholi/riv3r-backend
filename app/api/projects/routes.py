from fastapi import APIRouter, Depends, status

from app.api.projects import dependencies as deps
from app.api.projects import schemas, views
from app.core import dependencies as core_deps
from app.core.permissions import PermissionChecker
from app.services.projects import ProjectService

projects_router = APIRouter(prefix="/api/projects", tags=["Projects"])


@projects_router.post(
    "",
    response_model=views.Project,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    project: schemas.CreateProject,
    current_user: dict = Depends(core_deps.get_current_user),
    project_service: ProjectService = Depends(deps.get_project_service),
    permission_checkers: tuple[PermissionChecker, ...] = Depends(
        deps.get_create_project_permission_checkers
    ),
) -> dict:
    return await project_service.create_project(
        project, current_user, permission_checkers
    )


@projects_router.post(
    "/{project_id}/publish",
    response_model=views.Project,
)
async def publish_project(
    project_id: str,
    current_user: dict = Depends(core_deps.get_current_user),
    project_service: ProjectService = Depends(deps.get_project_service),
    permission_checkers: tuple[PermissionChecker, ...] = Depends(
        deps.get_create_project_permission_checkers
    ),
) -> dict:
    return await project_service.publish_project(
        project_id, current_user, permission_checkers
    )
