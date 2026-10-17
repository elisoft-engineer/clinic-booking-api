from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

Password = Annotated[str, StringConstraints(min_length=10, max_length=128)]
FullName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)
]


class PatientRegister(BaseModel):
    full_name: FullName
    email: EmailStr
    password: Password
    phone: str | None = Field(default=None, max_length=30)


class PatientLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: EmailStr
    phone: str | None
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    patient: PatientRead


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=512)


class LogoutResponse(BaseModel):
    status: str = "logged_out"
