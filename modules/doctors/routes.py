from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import DatabaseSession
from modules.doctors.schemas import AvailabilitySlot, DoctorRead
from modules.doctors.service import doctor_service

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("", response_model=list[DoctorRead])
async def list_doctors(
    session: DatabaseSession,
) -> list[DoctorRead]:
    return [
        DoctorRead.model_validate(item)
        for item in await doctor_service.list_doctors(session)
    ]


@router.get("/{doctor_id}", response_model=DoctorRead)
async def get_doctor(
    doctor_id: UUID,
    session: DatabaseSession,
) -> DoctorRead:
    doctor = await doctor_service.get_doctor(session, doctor_id)
    return DoctorRead.model_validate(doctor)


@router.get("/{doctor_id}/availability", response_model=list[AvailabilitySlot])
async def get_availability(
    doctor_id: UUID,
    date: Annotated[date, Query(description="Clinic-local date in YYYY-MM-DD format")],
    session: DatabaseSession,
) -> list[AvailabilitySlot]:
    return await doctor_service.availability(session, doctor_id, date)
