import enum
from pydantic import BaseModel, EmailStr, HttpUrl, Field, AfterValidator, computed_field, model_validator
from typing import Annotated, Optional

from app.utils import validators as vals


class OrganizationType(str, enum.Enum):
    client = "client"
    agency = "agency"


class OnboardOrganization(BaseModel):
    company_email: Annotated[
        EmailStr, Field(description="Email of the onboarding organization")
    ]
    registered_name: Annotated[
        str, Field(description="Name of the onboarding organization")
    ]
    website_url: Optional[HttpUrl] = Field(
        description="Website of the onboarding organization", default=None
    )
    industry: Annotated[
        str, Field(description="Industry of the onboarding organization")
    ]
    org_type: Annotated[
        OrganizationType,
        Field(description="Type of the onboarding organization"),
    ]
    owner: Annotated[
        "OnboardUser", Field(description="Owner info of the onboarding organization")
    ]

    @model_validator(mode="after")
    def same_domain_check(self):
        vals.validate_same_domain(self.company_email, self.owner.email)
        return self

PhoneNumber = Annotated[str, AfterValidator(vals.validate_phone_number)]
Password = Annotated[str, AfterValidator(vals.validate_password)]


class OnboardUser(BaseModel):
    email: Annotated[EmailStr, Field(description="Email of the onboarding user")]
    first_name: Annotated[str, Field(description="First name of the onboarding user")]
    last_name: Annotated[str, Field(description="Last name of the onboarding user")]

    @computed_field
    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    password: Annotated[Password, Field(description="Password of the onboarding user")]
    phone_number: Optional[PhoneNumber] = Field(
        description="Phone number of the onboarding user", default=None
    )


class OnboardResource(OnboardUser):
    title: Annotated[str, Field(description="Title of the onboarding resource")]
    bio: Optional[str] = Field(description="Bio of the onboarding resource", default=None)
    location: Optional[str] = Field(
        description="Location of the onboarding resource", default=None
    )
    skills: Annotated[list[str], Field(description="Skills of the onboarding resource")]
    experience_years: Annotated[
        int, Field(description="Experience years of the onboarding resource")
    ]
    portfolio_url: Optional[HttpUrl] = Field(
        description="Portfolio URL of the onboarding resource", default=None
    )
    linked_in_url: Optional[HttpUrl] = Field(
        description="Linkedin URL of the onboarding resource", default=None
    )

    @model_validator(mode="after")
    def different_url_check(self):
        if self.portfolio_url and self.linked_in_url and self.portfolio_url == self.linked_in_url:
            raise ValueError("Portfolio URL and LinkedIn URL cannot be the same")
        return self
