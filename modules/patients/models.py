from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database import BaseModel

if TYPE_CHECKING:
    from modules.appointments.models import Appointment


class Patient(BaseModel):
    __tablename__ = "patients"

    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(
        String(254), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="patient",
        lazy="raise",
    )
