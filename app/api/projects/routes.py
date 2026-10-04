from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.api.projects import dependencies as deps
from app.api.projects import schemas, views
from app.core import dependencies as core_deps
from app.core.permissions import PermissionChecker
from app.services.audit import AuditService
from app.services.projects import ProjectService

projects_router = APIRouter(prefix="/api/projects", tags=["Projects"])


@projects_router.get("", response_model=views.ProjectList)
async def list_projects(
    query: schemas.ProjectListQueryDependency,
    current_user: dict = Depends(core_deps.get_current_user),
    project_service: ProjectService = Depends(deps.get_project_service),
    permission_checker: PermissionChecker = Depends(
        deps.get_read_project_permission_checker
    ),
) -> dict:
    return await project_service.list_projects(query, current_user, permission_checker)


@projects_router.get("/{project_id}", response_model=views.Project)
async def get_project(
    project_id: UUID,
    current_user: dict = Depends(core_deps.get_current_user),
    project_service: ProjectService = Depends(deps.get_project_service),
    permission_checker: PermissionChecker = Depends(
        deps.get_read_project_permission_checker
    ),
) -> dict:
    return await project_service.get_project(
        str(project_id), current_user, permission_checker
    )


@projects_router.post(
    "",
    response_model=views.Project,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    req: Request,
    project: schemas.CreateProject,
    current_user: dict = Depends(core_deps.get_current_user),
    project_service: ProjectService = Depends(deps.get_project_service),
    audit_service: AuditService = Depends(core_deps.get_audit_service),
    permission_checkers: tuple[PermissionChecker, ...] = Depends(
        deps.get_create_project_permission_checkers
    ),
) -> dict:
    response = await project_service.create_project(
        project, current_user, permission_checkers
    )
    await audit_service.log(
        req,
        user_id=current_user["id"],
        entity_type="project",
        task_type="project_create",
    )
    return response


@projects_router.post(
    "/{project_id}/publish",
    response_model=views.Project,
)
async def publish_project(
    req: Request,
    project_id: str,
    current_user: dict = Depends(core_deps.get_current_user),
    project_service: ProjectService = Depends(deps.get_project_service),
    audit_service: AuditService = Depends(core_deps.get_audit_service),
    permission_checkers: tuple[PermissionChecker, ...] = Depends(
        deps.get_publish_project_permission_checkers
    ),
) -> dict:
    response = await project_service.publish_project(
        project_id, current_user, permission_checkers
    )
    await audit_service.log(
        req,
        user_id=current_user["id"],
        entity_type="project",
        task_type="project_publish",
    )
    return response
