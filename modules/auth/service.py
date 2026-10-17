from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.exceptions import AccountStateError, AuthenticationError, ConflictError
from core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from modules.auth.models import RefreshToken
from modules.auth.schemas import (
    LogoutResponse,
    PatientLogin,
    PatientRead,
    PatientRegister,
    RefreshTokenRequest,
    TokenResponse,
)
from modules.patients.models import Patient


def _utc(value: datetime) -> datetime:
    """Normalize SQLite's naive datetimes and database-aware datetimes to UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


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
        return await self._token_response(session, patient)

    async def login(self, session: AsyncSession, data: PatientLogin) -> TokenResponse:
        email = str(data.email).lower()
        patient = await session.scalar(select(Patient).where(Patient.email == email))
        if patient is None or not verify_password(data.password, patient.password_hash):
            raise AuthenticationError("Invalid email or password.")
        if not patient.is_active:
            raise AccountStateError("This patient account is inactive.")
        return await self._token_response(session, patient)

    async def refresh(
        self, session: AsyncSession, data: RefreshTokenRequest
    ) -> TokenResponse:
        old_hash = hash_refresh_token(data.refresh_token)
        stored = await session.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == old_hash)
            .with_for_update()
        )
        now = datetime.now(UTC)
        if (
            stored is None
            or stored.revoked_at is not None
            or _utc(stored.expires_at) <= now
        ):
            raise AuthenticationError("Invalid, expired, or revoked refresh token.")

        patient = await session.get(Patient, stored.patient_id)
        if patient is None or not patient.is_active:
            raise AccountStateError("This patient account is inactive.")

        # Rotate tokens on every refresh: the old token cannot be used again.
        stored.revoked_at = now
        await session.flush()
        return await self._token_response(session, patient)

    async def logout(
        self, session: AsyncSession, data: RefreshTokenRequest
    ) -> LogoutResponse:
        stored = await session.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == hash_refresh_token(data.refresh_token))
            .with_for_update()
        )
        # Idempotent response avoids disclosing whether a token exists.
        if stored is not None and stored.revoked_at is None:
            stored.revoked_at = datetime.now(UTC)
            await session.flush()
        return LogoutResponse()

    async def _token_response(
        self, session: AsyncSession, patient: Patient
    ) -> TokenResponse:
        refresh_token = create_refresh_token()
        refresh_expires_at = datetime.now(UTC) + timedelta(
            days=settings.refresh_token_lifetime_days
        )
        session.add(
            RefreshToken(
                token_hash=hash_refresh_token(refresh_token),
                patient_id=patient.id,
                expires_at=refresh_expires_at,
            )
        )
        await session.flush()
        return TokenResponse(
            access_token=create_access_token(patient.id),
            refresh_token=refresh_token,
            expires_in=settings.access_token_lifetime_minutes * 60,
            refresh_expires_in=settings.refresh_token_lifetime_days * 24 * 60 * 60,
            patient=PatientRead.model_validate(patient),
        )


auth_service = AuthService()
