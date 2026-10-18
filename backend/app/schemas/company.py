from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from backend.app.schemas.student_auth import validate_bcrypt_password_length


class CompanyCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    description: str | None = None
    contact_info: str | None = Field(default=None, max_length=255)

    validate_password_length = field_validator("password")(
        validate_bcrypt_password_length
    )


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    contact_info: str | None = Field(default=None, max_length=255)


class CompanyResponse(BaseModel):
    id: int
    email: EmailStr
    name: str
    city: str
    description: str | None
    contact_info: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
