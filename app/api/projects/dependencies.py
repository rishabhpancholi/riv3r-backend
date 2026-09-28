from fastapi import Depends
from supabase import AsyncClient

from app.core import dependencies as core_deps
from app.core.permissions import OrganizationLevelPermissionChecker, PermissionChecker
from app.repositories import contracts
from app.repositories import supabase as repositories
from app.services.projects import ProjectService


def get_projects(
    db: AsyncClient = Depends(core_deps.get_db),
) -> contracts.ProjectRepository:
    return repositories.SupabaseProjectRepository(db)


def get_project_service(
    projects: contracts.ProjectRepository = Depends(get_projects),
    memberships: contracts.MembershipRepository = Depends(core_deps.get_memberships),
) -> ProjectService:
    return ProjectService(projects=projects, memberships=memberships)


def get_create_project_permission_checkers(
    organizations: contracts.OrganizationRepository = Depends(
        core_deps.get_organizations
    ),
) -> tuple[PermissionChecker, ...]:
    return (
        OrganizationLevelPermissionChecker(
            organizations, allowed_org_types={"client"}
        ),
    )
