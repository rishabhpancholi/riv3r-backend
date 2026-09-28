from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class Project(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    org_id: UUID
    created_by_user_id: UUID
    spoc_user_id: UUID
    title: str
    description: str
    status: Literal["draft", "published", "closed", "cancelled"]
    deadline_date: date
    budget: Decimal
    currency: str
    published_at: datetime | None = None
    domain: str
    skill_tags: list[str]
