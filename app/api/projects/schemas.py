from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import Query
from pydantic import BaseModel, Field, field_validator


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class ProjectSortField(StrEnum):
    CREATED_AT = "created_at"
    DEADLINE_DATE = "deadline_date"
    PUBLISHED_AT = "published_at"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


def normalize_skill_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        value = tag.strip().lower()
        if not value:
            raise ValueError("Skill tags cannot be empty")
        if value not in seen:
            normalized.append(value)
            seen.add(value)
    return normalized


class CreateProject(BaseModel):
    spoc_user_id: UUID = Field(
        description="ID of the organization member responsible for the project"
    )
    title: str = Field(description="Title of the project", min_length=1)
    description: str = Field(
        description="Detailed project description", min_length=1
    )
    deadline_date: date = Field(
        description="Date by which the project should be completed"
    )
    budget: Decimal = Field(
        description="Project budget in the specified currency",
        ge=0,
        max_digits=15,
        decimal_places=2,
    )
    currency: str = Field(
        default="INR",
        description="Three-letter uppercase ISO currency code",
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
    )
    domain: str = Field(
        default="Not Specified",
        description="Business or technical domain of the project",
        min_length=1,
    )
    skill_tags: list[str] = Field(
        default_factory=list,
        description="Skills required to deliver the project",
    )
    publish_also: bool = Field(
        default=False,
        description="Publish the project immediately instead of saving it as a draft",
    )

    @field_validator("skill_tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return normalize_skill_tags(value)

    @field_validator("deadline_date")
    @classmethod
    def deadline_must_be_in_the_future(cls, value: date) -> date:
        if value <= date.today():
            raise ValueError("Deadline date must be later than today")
        return value


class ProjectListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="One-based result page")
    page_size: int = Field(
        default=20, ge=1, le=100, description="Projects returned per page"
    )
    org_id: UUID | None = Field(
        default=None, description="Exact organization filter available only to RIV3R"
    )
    spoc_user_id: UUID | None = Field(
        default=None, description="Exact project SPOC user ID filter"
    )
    status: ProjectStatus | None = Field(
        default=None, description="Exact project lifecycle status filter"
    )
    title: str | None = Field(
        default=None, description="Case-insensitive title substring"
    )
    description: str | None = Field(
        default=None, description="Case-insensitive description substring"
    )
    domain: str | None = Field(
        default=None, description="Case-insensitive domain substring"
    )
    skill_tags: list[str] = Field(
        default_factory=list,
        description="Repeated tags that must all be present on a matching project",
    )
    sort_by: ProjectSortField = Field(
        default=ProjectSortField.CREATED_AT, description="Project field used to sort"
    )
    sort_order: SortOrder = Field(
        default=SortOrder.DESC, description="Ascending or descending sort direction"
    )

    @field_validator("title", "description", "domain")
    @classmethod
    def normalize_text_filter(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Text filters cannot be empty")
        return value

    @field_validator("skill_tags")
    @classmethod
    def normalize_filter_tags(cls, value: list[str]) -> list[str]:
        return normalize_skill_tags(value)


ProjectListQueryDependency = Annotated[ProjectListQuery, Query()]
