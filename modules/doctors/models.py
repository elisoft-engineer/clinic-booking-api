from datetime import time
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database import BaseModel

if TYPE_CHECKING:
    from modules.appointments.models import Appointment


class Doctor(BaseModel):
    __tablename__ = "doctors"

    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    specialization: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    working_hours: Mapped[list["DoctorWorkingHour"]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan", lazy="raise"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="doctor", lazy="raise"
    )


class DoctorWorkingHour(BaseModel):
    __tablename__ = "doctor_working_hours"
    __table_args__ = (
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="weekday_range"),
        CheckConstraint("start_time < end_time", name="working_hour_order"),
        UniqueConstraint(
            "doctor_id",
            "weekday",
            "start_time",
            "end_time",
            name="doctor_working_interval",
        ),
    )

    doctor_id: Mapped[UUID] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # Monday=0, Sunday=6
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    doctor: Mapped[Doctor] = relationship(back_populates="working_hours", lazy="raise")
