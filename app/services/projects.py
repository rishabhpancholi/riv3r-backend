import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime

from app.api.projects import schemas
from app.core import exceptions
from app.core.permissions import PermissionChecker
from app.repositories.contracts import MembershipRepository, ProjectRepository
from app.services.project_embeddings import ProjectEmbeddingGenerator


class ProjectService:
    def __init__(
        self,
        *,
        projects: ProjectRepository,
        memberships: MembershipRepository,
        embedding_generator: ProjectEmbeddingGenerator,
    ):
        self.projects = projects
        self.memberships = memberships
        self.embedding_generator = embedding_generator

    async def create_project(
        self,
        project: schemas.CreateProject,
        current_user: dict,
        permission_checkers: Sequence[PermissionChecker],
    ) -> dict:
        decisions = await asyncio.gather(
            *(checker.check(current_user) for checker in permission_checkers)
        )
        has_cross_tenant_access = any(
            decision.cross_tenant for decision in decisions
        )
        spoc_is_member = has_cross_tenant_access or (
            await self.memberships.check_org_membership(
                current_user["org_id"], str(project.spoc_user_id)
            )
        )
        if not spoc_is_member:
            raise exceptions.PermissionError(
                detail="The SPOC user must belong to the project's organization"
            )

        project_data = project.model_dump(
            exclude={"publish_also"}, mode="json"
        ) | {
            "org_id": current_user["org_id"],
            "created_by_user_id": current_user["id"],
        }
        if project.publish_also:
            embedding = await self.embedding_generator.generate(project_data)
            project_data.update(
                status="published", published_at=datetime.now(UTC).isoformat()
            )
            if embedding is not None:
                project_data.update(
                    project_embeddings=embedding.vector,
                    embedding_model=embedding.model,
                    embedded_at=datetime.now(UTC).isoformat(),
                )

        return await self.projects.store_project(project_data)

    async def publish_project(
        self,
        project_id: str,
        current_user: dict,
        permission_checkers: Sequence[PermissionChecker],
    ) -> dict:
        results = await asyncio.gather(
            self.projects.get_project_by_id(project_id),
            *(checker.check(current_user) for checker in permission_checkers),
            return_exceptions=True,
        )
        project = results[0]
        if isinstance(project, BaseException):
            raise project
        if not project:
            raise exceptions.NotFoundError("project")

        decisions = []
        for result in results[1:]:
            if isinstance(result, BaseException):
                raise result
            decisions.append(result)

        has_cross_tenant_access = any(
            decision.cross_tenant for decision in decisions
        )
        if (
            not has_cross_tenant_access
            and project["org_id"] != current_user["org_id"]
        ):
            raise exceptions.PermissionError(
                detail="You cannot publish a project from another organization"
            )
        if project["status"] != "draft":
            raise exceptions.StateError("Only draft projects can be published")

        embedding = await self.embedding_generator.generate(project)
        embedded_at = datetime.now(UTC).isoformat() if embedding is not None else None
        published = await self.projects.publish_draft(
            project_id,
            datetime.now(UTC).isoformat(),
            embedding=embedding.vector if embedding is not None else None,
            embedding_model=embedding.model if embedding is not None else None,
            embedded_at=embedded_at,
            organization_id=(
                None if has_cross_tenant_access else current_user["org_id"]
            ),
        )
        if published:
            return published

        current = await self.projects.get_project_by_id(project_id)
        if not current:
            raise exceptions.NotFoundError("project")
        if (
            not has_cross_tenant_access
            and current["org_id"] != current_user["org_id"]
        ):
            raise exceptions.PermissionError(
                detail="You cannot publish a project from another organization"
            )
        raise exceptions.StateError("Only draft projects can be published")
