from fastapi import Depends
from supabase import AsyncClient

from app.clients.contracts import EmbeddingsClient
from app.core import dependencies as core_deps
from app.core.config import load_settings
from app.core.permissions import OrganizationLevelPermissionChecker, PermissionChecker
from app.repositories import contracts
from app.repositories import supabase as repositories
from app.services.projects import ProjectService
from app.services.project_embeddings import ProjectEmbeddingGenerator


def get_projects(
    db: AsyncClient = Depends(core_deps.get_db),
) -> contracts.ProjectRepository:
    return repositories.SupabaseProjectRepository(db)


def get_project_embedding_generator(
    embeddings: EmbeddingsClient = Depends(core_deps.get_embeddings),
    fallback_embeddings: EmbeddingsClient = Depends(
        core_deps.get_fallback_embeddings
    ),
) -> ProjectEmbeddingGenerator:
    settings = load_settings()
    return ProjectEmbeddingGenerator(
        embeddings=embeddings,
        fallback_embeddings=fallback_embeddings,
        primary_model=settings.embeddings_model,
        fallback_model=settings.embeddings_fallback_model,
    )


def get_project_service(
    projects: contracts.ProjectRepository = Depends(get_projects),
    memberships: contracts.MembershipRepository = Depends(core_deps.get_memberships),
    embedding_generator: ProjectEmbeddingGenerator = Depends(
        get_project_embedding_generator
    ),
) -> ProjectService:
    return ProjectService(
        projects=projects,
        memberships=memberships,
        embedding_generator=embedding_generator,
    )


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
