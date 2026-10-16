from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AppointmentCreate(BaseModel):
    doctor_id: UUID
    starts_at: datetime

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("starts_at must include a timezone offset.")
        return value


class AppointmentReschedule(BaseModel):
    starts_at: datetime

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("starts_at must include a timezone offset.")
        return value


class AppointmentCancel(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError(
                "Cancellation reason must contain at least 3 non-space characters."
            )
        return value


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patient_id: UUID
    doctor_id: UUID
    starts_at: datetime
    ends_at: datetime
    status: str
    cancellation_reason: str | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime
