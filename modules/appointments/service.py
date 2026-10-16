from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from modules.appointments.models import Appointment
from modules.appointments.schemas import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentReschedule,
)
from modules.doctors.models import Doctor, DoctorWorkingHour
from modules.patients.models import Patient
from shared.enums import AppointmentStatus

SLOT_DURATION = timedelta(minutes=30)
BOOKING_CUTOFF = timedelta(hours=1)


class AppointmentService:
    async def book(
        self,
        session: AsyncSession,
        patient: Patient,
        data: AppointmentCreate,
    ) -> Appointment:
        doctor = await self._get_active_doctor(session, data.doctor_id)
        starts_at = data.starts_at.astimezone(UTC)
        await self._validate_slot(session, doctor, starts_at)

        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            starts_at=starts_at,
            ends_at=starts_at + SLOT_DURATION,
            status=AppointmentStatus.BOOKED.value,
        )
        session.add(appointment)
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError("That appointment slot has just been booked.") from exc
        return appointment

    async def cancel(
        self,
        session: AsyncSession,
        patient: Patient,
        appointment_id: UUID,
        data: AppointmentCancel,
    ) -> Appointment:
        appointment = await self._get_owned_appointment(
            session, patient.id, appointment_id
        )
        if appointment.status == AppointmentStatus.CANCELLED.value:
            raise ConflictError("This appointment has already been cancelled.")

        appointment.status = AppointmentStatus.CANCELLED.value
        appointment.cancellation_reason = data.reason
        appointment.cancelled_at = datetime.now(UTC)
        await session.flush()
        return appointment

    async def reschedule(
        self,
        session: AsyncSession,
        patient: Patient,
        appointment_id: UUID,
        data: AppointmentReschedule,
    ) -> Appointment:
        appointment = await self._get_owned_appointment(
            session, patient.id, appointment_id
        )
        if appointment.status == AppointmentStatus.CANCELLED.value:
            raise ConflictError("A cancelled appointment cannot be rescheduled.")

        starts_at = data.starts_at.astimezone(UTC)
        doctor = await self._get_active_doctor(session, appointment.doctor_id)
        await self._validate_slot(
            session,
            doctor,
            starts_at,
            exclude_appointment_id=appointment.id,
        )

        appointment.starts_at = starts_at
        appointment.ends_at = starts_at + SLOT_DURATION
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError("That appointment slot has just been booked.") from exc
        return appointment

    async def get_owned(
        self, session: AsyncSession, patient: Patient, appointment_id: UUID
    ) -> Appointment:
        return await self._get_owned_appointment(session, patient.id, appointment_id)

    async def list_patient_appointments(
        self,
        session: AsyncSession,
        patient: Patient,
        upcoming_only: bool = False,
    ) -> list[Appointment]:
        statement = select(Appointment).where(Appointment.patient_id == patient.id)
        if upcoming_only:
            statement = statement.where(
                Appointment.status == AppointmentStatus.BOOKED.value,
                Appointment.starts_at >= datetime.now(UTC),
            )
        result = await session.scalars(statement.order_by(Appointment.starts_at.asc()))
        return list(result.all())

    async def _get_active_doctor(
        self, session: AsyncSession, doctor_id: UUID
    ) -> Doctor:
        doctor = await session.get(Doctor, doctor_id)
        if doctor is None or not doctor.is_active:
            raise NotFoundError("Doctor not found.")
        return doctor

    async def _get_owned_appointment(
        self, session: AsyncSession, patient_id: UUID, appointment_id: UUID
    ) -> Appointment:
        result = await session.scalar(
            select(Appointment).where(
                Appointment.id == appointment_id,
                Appointment.patient_id == patient_id,
            )
        )
        if result is None:
            # Avoid disclosing whether another patient's appointment exists.
            raise NotFoundError("Appointment not found.")
        return result

    async def _validate_slot(
        self,
        session: AsyncSession,
        doctor: Doctor,
        starts_at: datetime,
        exclude_appointment_id: UUID | None = None,
    ) -> None:
        now = datetime.now(UTC)
        if starts_at <= now:
            raise BusinessRuleError("Appointments cannot be booked in the past.")
        if starts_at < now + BOOKING_CUTOFF:
            raise BusinessRuleError(
                "Appointments must be booked at least one hour in advance."
            )

        local_start = starts_at.astimezone(settings.clinic_zone)
        if local_start.second != 0 or local_start.microsecond != 0:
            raise BusinessRuleError(
                "Appointment start time must be on a 30-minute boundary."
            )
        if local_start.minute not in (0, 30):
            raise BusinessRuleError(
                "Appointment start time must be on a 30-minute boundary."
            )

        slot_end = starts_at + SLOT_DURATION
        local_end = slot_end.astimezone(settings.clinic_zone)
        if local_start.date() != local_end.date():
            raise BusinessRuleError("Appointments must fit within the same day.")

        schedule_result = await session.scalars(
            select(DoctorWorkingHour).where(
                DoctorWorkingHour.doctor_id == doctor.id,
                DoctorWorkingHour.weekday == local_start.weekday(),
            )
        )
        local_start_time = local_start.timetz().replace(tzinfo=None)
        local_end_time = local_end.timetz().replace(tzinfo=None)
        valid_schedule = any(
            item.start_time <= local_start_time and local_end_time <= item.end_time
            for item in schedule_result.all()
        )
        if not valid_schedule:
            raise BusinessRuleError(
                "The selected slot is outside the doctor's working hours."
            )

        conflict_statement = select(Appointment.id).where(
            Appointment.doctor_id == doctor.id,
            Appointment.status == AppointmentStatus.BOOKED.value,
            Appointment.starts_at < slot_end,
            Appointment.ends_at > starts_at,
        )
        if exclude_appointment_id is not None:
            conflict_statement = conflict_statement.where(
                Appointment.id != exclude_appointment_id
            )
        conflict = await session.scalar(conflict_statement)
        if conflict is not None:
            raise ConflictError("That appointment slot is already booked.")


appointment_service = AppointmentService()
