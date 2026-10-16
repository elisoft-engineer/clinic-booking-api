from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.exceptions import AuthenticationError, ConflictError
from core.security import create_access_token, hash_password, verify_password
from modules.auth.schemas import (
    PatientLogin,
    PatientRead,
    PatientRegister,
    TokenResponse,
)
from modules.patients.models import Patient


class AuthService:
    async def register(
        self, session: AsyncSession, data: PatientRegister
    ) -> TokenResponse:
        email = str(data.email).lower()
        existing = await session.scalar(
            select(Patient.id).where(Patient.email == email)
        )
        if existing is not None:
            raise ConflictError("An account with this email already exists.")

        patient = Patient(
            full_name=data.full_name,
            email=email,
            password_hash=hash_password(data.password),
            phone=data.phone,
        )
        session.add(patient)
        await session.flush()
        return self._token_response(patient)

    async def login(self, session: AsyncSession, data: PatientLogin) -> TokenResponse:
        email = str(data.email).lower()
        patient = await session.scalar(select(Patient).where(Patient.email == email))
        if patient is None or not verify_password(data.password, patient.password_hash):
            raise AuthenticationError("Invalid email or password.")
        if not patient.is_active:
            raise AuthenticationError("This patient account is inactive.")
        return self._token_response(patient)

    @staticmethod
    def _token_response(patient: Patient) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(patient.id),
            expires_in=settings.access_token_lifetime_minutes * 60,
            patient=PatientRead(
                id=patient.id,
                full_name=patient.full_name,
                email=patient.email,
                phone=patient.phone,
                is_active=patient.is_active,
            ),
        )


auth_service = AuthService()
