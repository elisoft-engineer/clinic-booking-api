from fastapi import APIRouter

from core.dependencies import CurrentPatient, DatabaseSession
from modules.auth.schemas import (
    PatientLogin,
    PatientRead,
    PatientRegister,
    TokenResponse,
)
from modules.auth.service import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    data: PatientRegister,
    session: DatabaseSession,
) -> TokenResponse:
    return await auth_service.register(session, data)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: PatientLogin,
    session: DatabaseSession,
) -> TokenResponse:
    return await auth_service.login(session, data)


@router.get("/me", response_model=PatientRead)
async def me(patient: CurrentPatient) -> PatientRead:
    return PatientRead.model_validate(patient)
