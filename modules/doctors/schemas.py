from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DoctorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    specialization: str | None
    is_active: bool


class AvailabilitySlot(BaseModel):
    starts_at: datetime
    ends_at: datetime
