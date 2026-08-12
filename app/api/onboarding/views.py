import uuid
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class RowMixin(BaseModel):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class Organization(RowMixin):
    company_email: str
    registered_name: str
    website_url: Optional[str] = None
    industry: str
    is_verified: bool
    org_type: Literal["client", "agency", "riv3r"]
    owner: "User"


class User(RowMixin):
    email: str
    name: str
    is_verified: bool
    phone_number: Optional[str] = None
    is_resource: bool
    org_id: Optional[str] = None
    is_owner: Optional[bool] = None


class Resource(User):
    title: str
    bio: Optional[str] = None
    location: Optional[str] = None
    skills: list[str]
    experience_years: int
    portfolio_url: Optional[str] = None
    linked_in_url: Optional[str] = None
    is_available: bool
