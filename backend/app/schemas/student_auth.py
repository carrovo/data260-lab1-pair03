from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StudentSignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=100)


class StudentLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


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