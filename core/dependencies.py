from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.exceptions import AccountStateError, AuthenticationError
from core.security import decode_access_token
from modules.patients.models import Patient

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_patient(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Patient:
    if credentials is None:
        raise AuthenticationError("A bearer access token is required.")
    patient_id: UUID = decode_access_token(credentials.credentials)
    patient = await session.get(Patient, patient_id)
    if patient is None:
        raise AuthenticationError("Invalid or expired access token.")
    if not patient.is_active:
        raise AccountStateError("This patient account is inactive.")
    return patient


# The following ensure that we dont have to repeat the deps calls and
# therefore cleaner code
CurrentPatient = Annotated[Patient, Depends(get_current_patient)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
