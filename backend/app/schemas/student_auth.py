from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


MAX_BCRYPT_PASSWORD_BYTES = 72


def validate_bcrypt_password_length(password: str) -> str:
    if len(password.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES:
        raise ValueError(
            "Password must not exceed 72 UTF-8 bytes."
        )

    return password


class StudentSignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=100)

    validate_password_length = field_validator("password")(
        validate_bcrypt_password_length
    )


class StudentLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)

    validate_password_length = field_validator("password")(
        validate_bcrypt_password_length
    )


class StudentResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    city: str

    model_config = ConfigDict(from_attributes=True)


class StudentTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    student: StudentResponse
