from pydantic import BaseModel, EmailStr, HttpUrl, Field, computed_field, model_validator
from typing import Optional

from app.api.onboarding.schemas import Password, PhoneNumber


class UpdateUser(BaseModel):
    email: Optional[EmailStr] = Field(description="Email of the user", default=None)
    first_name: Optional[str] = Field(description="First name of the user", default=None)
    last_name: Optional[str] = Field(description="Last name of the user", default=None)

    @computed_field
    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    password: Optional[Password] = Field(description="Password of the user", default=None)
    phone_number: Optional[PhoneNumber] = Field(
        description="Phone number of the user", default=None
    )

    @model_validator(mode="after")
    def not_empty_check(self):
        if not self.model_dump(exclude_none=True, exclude={"name"}):
            raise ValueError("At least one field must be provided for update")
        return self


class UpdateOrganization(BaseModel):
    company_email: Optional[EmailStr] = Field(
        description="Email of the organization", default=None
    )
    registered_name: Optional[str] = Field(
        description="Name of the organization", default=None
    )
    website_url: Optional[HttpUrl] = Field(
        description="Website of the organization", default=None
    )
    industry: Optional[str] = Field(
        description="Industry of the organization", default=None
    )

    @model_validator(mode="after")
    def not_empty_check(self):
        if not self.model_dump(exclude_none=True):
            raise ValueError("At least one field must be provided for update")
        return self


class UpdateResource(BaseModel):
    title: Optional[str] = Field(description="Title of the resource", default=None)
    bio: Optional[str] = Field(description="Bio of the resource", default=None)
    location: Optional[str] = Field(description="Location of the resource", default=None)
    skills: Optional[list[str]] = Field(description="Skills of the resource", default=None)
    experience_years: Optional[int] = Field(
        description="Experience years of the resource", default=None
    )
    portfolio_url: Optional[HttpUrl] = Field(
        description="Portfolio URL of the resource", default=None
    )
    linked_in_url: Optional[HttpUrl] = Field(
        description="Linkedin URL of the resource", default=None
    )
    is_available: Optional[bool] = Field(
        description="Availability of the resource", default=None
    )

    @model_validator(mode="after")
    def not_empty_check(self):
        if not self.model_dump(exclude_none=True):
            raise ValueError("At least one field must be provided for update")
        return self

    @model_validator(mode="after")
    def different_url_check(self):
        if self.portfolio_url and self.linked_in_url and self.portfolio_url == self.linked_in_url:
            raise ValueError("Portfolio URL and LinkedIn URL cannot be the same")
        return self
