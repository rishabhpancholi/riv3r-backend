from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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

    @field_validator("deadline_date")
    @classmethod
    def deadline_must_be_in_the_future(cls, value: date) -> date:
        if value <= date.today():
            raise ValueError("Deadline date must be later than today")
        return value
