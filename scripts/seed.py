"""Seed a small set of doctors and weekday working hours.

Run with: poetry run python -m scripts.seed
"""

import asyncio
from datetime import time

from sqlalchemy import select

from core.database import SessionFactory, engine
from core.database import SessionFactory, engine
from modules.appointments import models as appointment_models
from modules.doctors import models as doctor_models
from modules.patients import models as patient_models

DOCTORS = [
    ("Dr. Amina Wanjiku", "General Practice"),
    ("Dr. Brian Otieno", "Family Medicine"),
    ("Dr. Cynthia Mwangi", "Paediatrics"),
    ("Dr. Daniel Kiptoo", "Dermatology"),
    ("Dr. Esther Njeri", "Gynaecology"),
]


async def seed() -> None:
    async with SessionFactory() as session:
        async with session.begin():
            for name, specialization in DOCTORS:
                doctor = await session.scalar(
                    select(doctor_models.Doctor).where(
                        doctor_models.Doctor.full_name == name
                    )
                )
                if doctor is None:
                    doctor = doctor_models.Doctor(
                        full_name=name, specialization=specialization
                    )
                    session.add(doctor)
                    await session.flush()
                    # Monday-Friday, 09:00-17:00; slots are 30 minutes.
                    for weekday in range(5):
                        existing_hours = await session.scalar(
                            select(doctor_models.DoctorWorkingHour).where(
                                doctor_models.DoctorWorkingHour.doctor_id == doctor.id,
                                doctor_models.DoctorWorkingHour.weekday == weekday,
                            )
                        )

                        if existing_hours is None:
                            session.add(
                                doctor_models.DoctorWorkingHour(
                                    doctor_id=doctor.id,
                                    weekday=weekday,
                                    start_time=time(9, 0),
                                    end_time=time(17, 0),
                                )
                            )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
