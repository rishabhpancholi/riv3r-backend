import asyncio
import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from pydantic import ValidationError

from app.api.projects import schemas, views
from app.core import exceptions
from app.core.permissions import PermissionChecker
from app.repositories.contracts import (
    MembershipRepository,
    OrganizationRepository,
    ProjectCache,
    ProjectRepository,
)
from app.services.project_embeddings import ProjectEmbeddingGenerator


logger = logging.getLogger(__name__)


class ProjectService:
    def __init__(
        self,
        *,
        projects: ProjectRepository,
        memberships: MembershipRepository,
        organizations: OrganizationRepository,
        cache: ProjectCache,
        embedding_generator: ProjectEmbeddingGenerator,
    ):
        self.projects = projects
        self.memberships = memberships
        self.organizations = organizations
        self.cache = cache
        self.embedding_generator = embedding_generator

    @staticmethod
    def _validated_project(project: dict) -> dict:
        return views.Project.model_validate(project).model_dump(mode="json")

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

        created = await self.projects.store_project(project_data)
        await self.cache.invalidate(None, str(created["org_id"]))
        return created

    async def get_project(
        self,
        project_id: str,
        current_user: dict,
        permission_checker: PermissionChecker,
    ) -> dict:
        decision = await permission_checker.check(current_user)
        organization_id = None if decision.cross_tenant else current_user["org_id"]

        cache_key, cached = await self.cache.get_detail(project_id)
        if cached is not None:
            try:
                project = self._validated_project(cached)
                if organization_id is None or project["org_id"] == organization_id:
                    return project
                raise exceptions.NotFoundError("project")
            except ValidationError:
                logger.warning("Ignoring invalid project cache for id=%s", project_id)

        project = await self.projects.get_visible_project(project_id, organization_id)
        if not project:
            raise exceptions.NotFoundError("project")
        validated = self._validated_project(project)
        if cache_key is not None:
            await self.cache.set_detail(cache_key, validated)
        return validated

    async def list_projects(
        self,
        query: schemas.ProjectListQuery,
        current_user: dict,
        permission_checker: PermissionChecker,
    ) -> dict:
        decision = await permission_checker.check(current_user)
        requested_org_id = str(query.org_id) if query.org_id is not None else None
        if not decision.cross_tenant and requested_org_id is not None:
            raise exceptions.PermissionError(
                detail="Only RIV3R users can filter projects by organization"
            )
        if decision.cross_tenant and requested_org_id is not None:
            organization = await self.organizations.get_organization_by_id(
                requested_org_id
            )
            if not organization:
                raise exceptions.NotFoundError("organization")

        organization_id = (
            requested_org_id if decision.cross_tenant else current_user["org_id"]
        )
        scope = f"org:{organization_id}" if organization_id else "global"
        cache_query = query.model_dump(mode="json", exclude={"org_id"})
        cache_key, cached = await self.cache.get_list(scope, cache_query)
        if cached is not None:
            try:
                return views.ProjectList.model_validate(cached).model_dump(mode="json")
            except ValidationError:
                logger.warning(
                    "Ignoring invalid project-list cache for scope=%s", scope
                )

        rows, total = await self.projects.list_projects(
            organization_id=organization_id,
            spoc_user_id=(
                str(query.spoc_user_id) if query.spoc_user_id is not None else None
            ),
            status=query.status.value if query.status is not None else None,
            title=query.title,
            description=query.description,
            domain=query.domain,
            skill_tags=query.skill_tags,
            sort_by=query.sort_by.value,
            sort_order=query.sort_order.value,
            offset=(query.page - 1) * query.page_size,
            limit=query.page_size,
        )
        result = views.ProjectList(
            items=[views.Project.model_validate(row) for row in rows],
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=(total + query.page_size - 1) // query.page_size,
        ).model_dump(mode="json")
        if cache_key is not None:
            await self.cache.set_list(cache_key, result)
        return result

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
            await self.cache.invalidate(
                project_id, str(published["org_id"])
            )
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
