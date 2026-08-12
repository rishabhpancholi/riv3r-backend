from pydantic import BaseModel, EmailStr, Field
from typing import Annotated

class LoginUser(BaseModel):
    email: Annotated[EmailStr, Field(description="Email of the user")]
    password: Annotated[str, Field(description="Password of the user")]


