from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database import BaseModel
from shared.enums import AppointmentStatus

if TYPE_CHECKING:
    from modules.doctors.models import Doctor
    from modules.patients.models import Patient


class Appointment(BaseModel):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('booked', 'cancelled')", name="appointment_status_valid"
        ),
        CheckConstraint("ends_at > starts_at", name="appointment_end_after_start"),
        Index(
            "uq_appointments_doctor_active_start",
            "doctor_id",
            "starts_at",
            unique=True,
            postgresql_where=text("status = 'booked'"),
            sqlite_where=text("status = 'booked'"),
        ),
        Index("ix_appointments_patient_starts_at", "patient_id", "starts_at"),
        Index("ix_appointments_doctor_starts_at", "doctor_id", "starts_at"),
    )

    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False
    )
    doctor_id: Mapped[UUID] = mapped_column(
        ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AppointmentStatus.BOOKED.value,
        server_default=AppointmentStatus.BOOKED.value,
    )
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    patient: Mapped["Patient"] = relationship(
        back_populates="appointments", lazy="raise"
    )
    doctor: Mapped["Doctor"] = relationship(back_populates="appointments", lazy="raise")
