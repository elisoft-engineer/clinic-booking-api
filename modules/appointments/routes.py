from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from core.dependencies import CurrentPatient, DatabaseSession
from modules.appointments.schemas import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentRead,
    AppointmentReschedule,
)
from modules.appointments.service import appointment_service

router = APIRouter(tags=["Appointments"])


@router.post(
    "/appointments", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED
)
async def book_appointment(
    data: AppointmentCreate,
    patient: CurrentPatient,
    session: DatabaseSession,
) -> AppointmentRead:
    appointment = await appointment_service.book(session, patient, data)
    return AppointmentRead.model_validate(appointment)


@router.get("/appointments/{appointment_id}", response_model=AppointmentRead)
async def get_appointment(
    appointment_id: UUID,
    patient: CurrentPatient,
    session: DatabaseSession,
) -> AppointmentRead:
    appointment = await appointment_service.get_owned(session, patient, appointment_id)
    return AppointmentRead.model_validate(appointment)


@router.patch("/appointments/{appointment_id}/cancel", response_model=AppointmentRead)
async def cancel_appointment(
    appointment_id: UUID,
    data: AppointmentCancel,
    patient: CurrentPatient,
    session: DatabaseSession,
) -> AppointmentRead:
    appointment = await appointment_service.cancel(
        session, patient, appointment_id, data
    )
    return AppointmentRead.model_validate(appointment)


@router.patch(
    "/appointments/{appointment_id}/reschedule", response_model=AppointmentRead
)
async def reschedule_appointment(
    appointment_id: UUID,
    data: AppointmentReschedule,
    patient: CurrentPatient,
    session: DatabaseSession,
) -> AppointmentRead:
    appointment = await appointment_service.reschedule(
        session, patient, appointment_id, data
    )
    return AppointmentRead.model_validate(appointment)


@router.get("/patients/{patient_id}/appointments", response_model=list[AppointmentRead])
async def list_patient_appointments(
    patient_id: UUID,
    patient: CurrentPatient,
    session: DatabaseSession,
    upcoming: Annotated[bool, Query()] = True,
) -> list[AppointmentRead]:
    if patient_id != patient.id:
        from core.exceptions import AuthorizationError

        raise AuthorizationError("You can only view your own appointments.")
    appointments = await appointment_service.list_patient_appointments(
        session, patient, upcoming_only=upcoming
    )
    return [AppointmentRead.model_validate(item) for item in appointments]
