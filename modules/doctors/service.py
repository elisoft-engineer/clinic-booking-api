from datetime import UTC, date, datetime, time, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from core.config import settings
from core.exceptions import NotFoundError
from modules.appointments.models import Appointment
from modules.doctors.models import Doctor, DoctorWorkingHour
from modules.doctors.schemas import AvailabilitySlot
from shared.enums import AppointmentStatus


class DoctorService:
    async def list_doctors(self, session: AsyncSession) -> list[Doctor]:
        result = await session.scalars(
            select(Doctor).where(Doctor.is_active.is_(True)).order_by(Doctor.full_name)
        )
        return list(result.all())

    async def get_doctor(self, session: AsyncSession, doctor_id: UUID) -> Doctor:
        doctor = await session.get(Doctor, doctor_id)
        if doctor is None or not doctor.is_active:
            raise NotFoundError("Doctor not found.")
        return doctor

    async def availability(
        self, session: AsyncSession, doctor_id: UUID, target_date: date
    ) -> list[AvailabilitySlot]:
        doctor = await self.get_doctor(session, doctor_id)
        del doctor  # Check if the doctor exists and their active status.

        zone = settings.clinic_zone
        day_start = datetime.combine(target_date, time.min, tzinfo=zone)
        day_end = day_start + timedelta(days=1)

        hours_result = await session.scalars(
            select(DoctorWorkingHour)
            .where(
                DoctorWorkingHour.doctor_id == doctor_id,
                DoctorWorkingHour.weekday == target_date.weekday(),
            )
            .order_by(DoctorWorkingHour.start_time)
        )
        intervals = list(hours_result.all())

        appointment_result = await session.scalars(
            select(Appointment.starts_at).where(
                Appointment.doctor_id == doctor_id,
                Appointment.status == AppointmentStatus.BOOKED.value,
                Appointment.starts_at >= day_start.astimezone(UTC),
                Appointment.starts_at < day_end.astimezone(UTC),
            )
        )
        booked = {
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
            for value in appointment_result.all()
        }

        now = datetime.now(UTC)
        cutoff = now + timedelta(hours=1)
        slots: list[AvailabilitySlot] = []
        for interval in intervals:
            cursor = datetime.combine(target_date, interval.start_time, tzinfo=zone)
            end = datetime.combine(target_date, interval.end_time, tzinfo=zone)
            # Slots begin on the clinic clock's :00 or :30 boundaries.
            if cursor.minute not in (0, 30) or cursor.second or cursor.microsecond:
                if cursor.minute < 30:
                    cursor = cursor.replace(minute=30, second=0, microsecond=0)
                else:
                    cursor = cursor.replace(
                        minute=0, second=0, microsecond=0
                    ) + timedelta(hours=1)
            while cursor + timedelta(minutes=30) <= end:
                slot_start = cursor.astimezone(UTC)
                slot_end = (cursor + timedelta(minutes=30)).astimezone(UTC)
                if slot_start > cutoff and slot_start not in booked:
                    slots.append(
                        AvailabilitySlot(
                            starts_at=slot_start,
                            ends_at=slot_end,
                        )
                    )
                cursor += timedelta(minutes=30)

        return slots


doctor_service = DoctorService()
