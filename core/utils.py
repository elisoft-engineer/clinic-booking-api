from typing import cast

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from core.config import settings
from core.exceptions import DomainError
from core.logger import logger


async def domain_error_handler(
    _: Request,
    exc: Exception,
) -> JSONResponse:
    """Exception handler for application errors"""
    exc = cast(DomainError, exc)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
    )


async def integrity_error_handler(
    _: Request,
    exc: Exception,
) -> JSONResponse:
    """Exception handler for database constraints violation"""
    exc = cast(IntegrityError, exc)

    original = getattr(exc, "orig", None)
    constraint_name = getattr(original, "constraint_name", None)
    message = str(original) if original is not None else ""

    known_conflict = constraint_name in {
        "ix_patients_email",
        "uq_patients_email",
        "uq_appointments_doctor_active_start",
        "uq_doctor_working_interval",
    } or any(
        marker in message
        for marker in (
            "patients.email",
            "patients_email_key",
            "uq_appointments_doctor_active_start",
        )
    )

    if known_conflict:
        logger.info("Known database uniqueness constraint rejected a request")
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "conflict",
                    "message": "The request conflicts with existing data.",
                }
            },
        )

    logger.exception("Unexpected database integrity failure")

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "database_error",
                "message": "A database operation failed.",
            }
        },
    )


async def database_error_handler(
    _: Request,
    exc: Exception,
) -> JSONResponse:
    """Exception handler for DB related errors"""
    exc = cast(SQLAlchemyError, exc)

    logger.exception("Database operation failed")

    message = "A database error occurred."
    if settings.debug:
        message = "A database error occurred. Check the server logs for details."

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "database_error",
                "message": message,
            }
        },
    )
