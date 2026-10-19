# Clinic Booking API

A clinic appointment booking API built with **FastAPI**, **SQLAlchemy**'s
async ORM, and **Alembic**. It supports patient authentication, doctor
discovery, availability lookup, and appointment booking, cancellation,
and rescheduling.

The focus is not just getting the endpoints to work. The implementation
is organized around clear module boundaries, request-level transaction
consistency, and database constraints that help protect booking
integrity when requests arrive concurrently.

## Contents

- [Why this stack](#why-this-stack)
- [What it supports](#what-it-supports)
- [Architecture](#architecture)
- [Key engineering decisions](#key-engineering-decisions)
- [Requirements](#requirements)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Database migrations and sample
  data](#database-migrations-and-sample-data)
- [Running the API and tests](#running-the-api-and-tests)
- [API reference](#api-reference)
- [Availability and booking rules](#availability-and-booking-rules)
- [AI-assisted development](#ai-assisted-development)
- [Possible next steps](#possible-next-steps)

## Why this stack

I chose **FastAPI** because of its lightweight ASGI foundation, native
support for asynchronous request handling, and automatic OpenAPI
documentation. It works naturally with async database
connections, and makes it possible to choose any ORM
without tightly coupling the application to the framework.

Django and Go are both strong options, depending on the context. Django
is particularly useful when a project benefits from its integrated ORM,
admin, and broader batteries-included convention. Go is a strong choice
for teams that want a compiled language, straightforward deployment, and
efficient concurrency. For this assessment, FastAPI offered a practical
balance of development speed, async support, low framework overhead,
and architectural flexibility.

## What it supports

- Patient registration and login.
- Short-lived access tokens and robust refresh-token rotation.
- Refresh-token revocation on logout.
- Authenticated patient detail lookup.
- Listing and retrieving of active doctors.
- Checking a doctor's available appointment slots for a clinic-local
  date.
- Booking, retrieving, cancelling, and rescheduling of appointments.
- Listing of a patient's appointments, with an option to include past or
  cancelled appointments.
- Centralized, consistent error responses.
- Database migrations and sample seed data.
- Automated asynchronous API tests that can be ran with pytest.

## Architecture

The codebase uses a **layered, modular design**. Each feature is grouped
by domain, while responsibilities remain separated within that feature.

```text
.
├── core/                   # Configuration, database, security, dependencies, errors
├── modules/
│   ├── auth/               # Registration, login, refresh, logout, current patient
│   ├── doctors/            # Doctor records and availability
│   ├── patients/           # Patient model
│   └── appointments/       # Booking lifecycle and appointment rules
├── shared/
│   ├── database.py         # Shared ORM base, IDs, timestamps, naming conventions
│   └── enums/              # Shared appointment status values
├── migrations/             # Alembic environment and schema revisions
├── scripts/
│   └── seed.py             # Repeatable doctor and working-hours seed
├── tests/                  # Async API and behavior tests
├── main.py                 # App creation, middleware, handlers, routers, lifespan
├── alembic.ini
└── pyproject.toml
```

A typical request moves through these responsibilities:

1.  **Route layer** --- validates the HTTP request and defines the API
    contract.
2.  **Service layer** --- applies business rules and coordinates the
    operations.
3.  **SQLAlchemy models** --- define models, relationships, and database
    constraints.
4.  **Database dependency** --- provides the request-scoped async
    session and transaction.

Schemas define the input and output contracts. Shared configuration,
authentication helpers, dependencies, exception types, and logging live
in `core/` so that feature modules do not need to reimplement them.

This separation makes things easier to locate and test, and it makes the
project scalable by avoiding concentration of all logic in route handlers
or one large service.

## Key engineering decisions

### One transaction per request

The database dependency opens a session and transaction for the request.
Routes and services share that session instead of starting and
committing independent transactions inside each service method.

I chose this because a request may need to coordinate more than one
service operation. If each operation is committed independently, an
operation might remain committed even if a another one failed. A
request-level transaction keeps those database changes atomic such
that successful requests commit, while if there's an exception the
transaction rolls back.

Services can flush when they need the database to evaluate pending
changes or constraints, but they do not independently decide the
request's commit boundary.

### Database constraints protect booking integrity

The application checks that a requested slot is valid, falls within the
doctor's working hours, meets the advance-booking cutoff (of 1 hour), and does not
overlap an existing booked appointment. The database adds a partial
unique index for a doctor's booked appointment start time, and checks
on appointment status and start/end ordering.

The application and database checks serve different purposes.
Application validation provides clear domain errors while database
constraints act as a final guard against conflicting writes, including
concurrent requests. Since bookings use fixed 30-minute slots aligned to
half-hour boundaries, the unique booked-start constraint prevents two
active bookings for the same doctor's slot. The application also checks
interval overlap explicitly.

### Refresh tokens are stored as hashes

Refresh tokens are randomized values. The raw token is returned
to the client, but the database stores its SHA-256 hash rather than the
reusable token itself. Refreshing rotates the token, and the previous
token cannot be reused. Logout revokes the stored token. This limits the
value of a database leak and helps prevent refresh-token replay.

Passwords are hashed with Argon2. Access tokens are signed JWTs with an
expiry and an explicit token type.

### Availability is computed in the clinic's time zone

Availability is based on each doctor's configured working hours and
existing booked appointments. The algorithm creates 30-minute slots on
the clinic clock, converts slot times to UTC for comparisons and API
output, excludes already-booked slots, and omits slots that begin within
the one-hour booking cutoff.

The clinic time zone is configurable and has a default value of `Africa/Nairobi`.
Keeping the clinic's local schedule separate from UTC timestamps and this avoids
treating a clinic's opening hours as if they were UTC hours.

### Annotated dependencies reduce repetition

Common dependencies such as the current authenticated patient and
database session are exposed as annotated types. Route dependecy injenction stay
concise, while authentication and session lifecycle remain defined
globally.

### Centralized exception handling

Expected domain errors share a common base class and are handled at
application level. Database integrity and SQLAlchemy errors also have
centralized handlers. This keeps routes focused on the request rather
than repeating `try/except` and response formatting. This gives
clients a consistent error structure.

## Requirements

- Python version compatible with the project dependencies (the project
  is developed and tested in a Python 3.14 environment).
- Poetry.
- A database supported by the configured SQLAlchemy async driver.
  SQLite with `aiosqlite` is convenient for local development and
  tests while PostgreSQL with `asyncpg` is suitable for both development and production environments.

## Getting started

### 1. Get the project and install dependencies

From the project root:

```bash
poetry install --no-root
```

Activate the virtual environment if you prefer:

```bash
poetry env activate
```

Use the activation command printed by Poetry for your shell, or run
commands with `poetry run`.

### 2. Configure environment variables

Create a `.env` file in the project root. For local SQLite development,
a minimal configuration is:

```dotenv
APP_NAME="Clinic Booking API"
APP_ENV=development
DEBUG=true

DATABASE_URL=sqlite+aiosqlite:///./clinic.db
SECRET_KEY=replace-this-with-a-long-random-secret

ALGORITHM=HS256
ACCESS_TOKEN_LIFETIME_MINUTES=30
REFRESH_TOKEN_LIFETIME_DAYS=7

TIMEZONE=Africa/Nairobi
CORS_ORIGINS=[]
```

`DATABASE_URL` and `SECRET_KEY` are required. Generate a strong secret
for local use, for example:

```bash
poetry run python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Do not commit a real `.env` file or production secrets. Keep
`DEBUG=false` in production and configure `CORS_ORIGINS` for the exact
browser origins that should be allowed. For PostgreSQL, use the async
SQLAlchemy URL form, for example
`postgresql+asyncpg://user:password@localhost:5432/clinic_booking`.

### 3. Apply migrations

```bash
poetry run alembic upgrade head
```

The migrations create
or update tables and indexes without relying on application startup to
create production tables.

### 4. Seed sample doctors

```bash
poetry run python -m scripts.seed
```

The seed script adds the sample doctors and fills in missing weekday
working-hour rows without overwriting existing schedules. The default
sample schedule is Monday to Friday, 09:00--17:00 in the clinic's
configured time zone. Weekends therefore return no availability unless
weekend working hours are configured.

## Running the API and tests

Start the development server:

```bash
poetry run uvicorn main:app --reload
```

Then open:

- Swagger Docs: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Health check: `http://127.0.0.1:8000/health`

Run the test suite:

```bash
poetry run pytest
```

Tests use an isolated async SQLite database by default
(`test_clinic.db`) and override the application's database dependency.
You can set `TEST_DATABASE_URL` to point tests at another suitable test
database. **Do not point tests at a database containing data you need to keep**
because the test drops and recreates the tables.

## Configuration

---

Variable Purpose Default

---

`APP_NAME` API title `Clinic Booking API`

`APP_ENV` Environment label `development`

`DEBUG` Enables debug logging `false`
and more diagnostic  
 database error messages

`DATABASE_URL` SQLAlchemy async Required
database URL

`SECRET_KEY` Secret used to sign Required
access tokens

`ALGORITHM` JWT signing algorithm `HS256`

`ACCESS_TOKEN_LIFETIME_MINUTES` Access-token lifetime `30`

`REFRESH_TOKEN_LIFETIME_DAYS` Refresh-token lifetime `7`

`TIMEZONE` IANA clinic time zone `Africa/Nairobi`

`CORS_ORIGINS` Allowed browser origins `[]`

---

The settings class validates the configured time zone and constrains
token lifetimes to reasonable ranges.

## API reference

All versioned endpoints are under `/api/v1`. The running OpenAPI
document at `/openapi.json` and Swagger UI at `/docs` are the definitive
interactive reference.

### Operations

Method Endpoint Purpose Auth

---

`GET` `/health` Health check No
`GET` `/` Basic API information and docs path No

### Authentication

---

Method Endpoint Purpose Auth

---

`POST` `/api/v1/auth/register` Register a No
patient and issue
tokens

`POST` `/api/v1/auth/login` Authenticate with No
email and  
 password

`POST` `/api/v1/auth/refresh` Rotate refresh No
token and issue  
 new tokens

`POST` `/api/v1/auth/logout` Revoke a refresh No
token

`GET` `/api/v1/auth/me` Get the Bearer access
authenticated token
patient

---

Example registration request:

```json
{
  "full_name": "Alex Mwangi",
  "email": "alex@example.com",
  "password": "choose-a-strong-password",
  "phone": "0712345678"
}
```

The phone field is optional. Use the `access_token` as
`Authorization: Bearer <access_token>` for protected endpoints. Keep the
refresh token secure and use it only with the refresh and logout
endpoints.

### Doctors and availability

---

Method Endpoint Purpose Auth

---

`GET` `/api/v1/doctors` List active No
doctors

`GET` `/api/v1/doctors/{doctor_id}` Get an active No
doctor

`GET` `/api/v1/doctors/{doctor_id}/availability?date=YYYY-MM-DD` Get available No
30-minute slots  
 for a  
 clinic-local date

---

Example:

```bash
curl "http://127.0.0.1:8000/api/v1/doctors/DOCTOR_UUID/availability?date=2026-10-19"
```

Availability returns a list of `starts_at` and `ends_at` timestamps.
Timestamps are returned in UTC; the `date` query parameter represents a
date in the clinic's configured time zone.

### Appointments

All appointment endpoints require a valid bearer access token and
operate on the authenticated patient's own appointments.

---

Method Endpoint Purpose

---

`POST` `/api/v1/appointments` Book an appointment

`GET` `/api/v1/appointments/{appointment_id}` Retrieve one of the
patient's appointments

`PATCH` `/api/v1/appointments/{appointment_id}/cancel` Cancel an appointment

`PATCH` `/api/v1/appointments/{appointment_id}/reschedule` Reschedule an
appointment

`GET` `/api/v1/patients/{patient_id}/appointments?upcoming=true` List the authenticated
patient's appointments

---

Example booking request:

```json
{
  "doctor_id": "DOCTOR_UUID",
  "starts_at": "2026-10-19T06:00:00Z"
}
```

Use a real doctor UUID and an actual slot returned by the availability
endpoint. Appointment timestamps
must include a timezone offset.

Example cancellation request:

```json
{
  "reason": "Unable to attend at the scheduled time"
}
```

Example rescheduling request:

```json
{
  "starts_at": "2026-10-19T06:30:00Z"
}
```

The patient ID in the appointment-list endpoint must match the
authenticated patient. Appointment lookup also scopes by patient,
avoiding disclosure of whether another patient's appointment exists.

## Availability and booking rules

- Appointments are 30 minutes long.
- Appointment start times must fall on `:00` or `:30` boundaries in
  the clinic's local time.
- The selected slot must fit within the doctor's working hours and
  must not cross into the next clinic-local day.
- Bookings must be made at least one hour before the start time.
- Past slots and already-booked slots are not offered as available.
- A cancelled appointment is not considered an active booking, so its
  slot can become available again if it still satisfies the other
  rules.
- A cancelled appointment cannot be cancelled again or rescheduled.
- A patient can only view or modify their own appointments.
- Requests that conflict with an existing booking return a conflict
  response rather than silently overwriting it.

## Error responses

Expected application errors use a consistent shape:

```json
{
  "error": {
    "code": "conflict",
    "message": "That appointment slot is already booked."
  }
}
```

Typical outcomes include:

- `400` --- business rule violation, such as booking outside working
  hours.
- `401` --- missing, invalid, or expired authentication.
- `403` --- forbidden operation or inactive account.
- `404` --- doctor, patient or appointment not found.
- `409` --- conflicting booking or duplicate data.
- `422` --- request data fails schema validation.
- `500` --- unexpected database failure.

Exact messages depend on the error path. In production, debug mode
should remain disabled so internal database details are not exposed to
clients.

## Where AI assisted in development

AI was used as a development aid, not as a substitute for engineering
judgment. It was particularly useful in three areas:

- **Exception handling:** It helped in shaping a global exception-handling
  convention that is registered on the FastAPI application, thereby replacing repeated
  error handling boilerplate with a consistent response
  contract.
- **Availability logic:** It also gave good insight into generating and
  filtering of 30-minute availability slots, as well as UTC conversion.
- **Seed data and tests:** It sped up the creation of
  sample data and automated tests.

I reviewed the suggestions and made the architectural decisions based on
the requirements. One explicit point of disagreement was **Transaction Ownership**:
AI suggested that service methods manage transactions
themselves. I kept decided to make transaction ownership request-scoped instead,
because it gives a single request one atomic
transaction even when the route coordinates multiple service operations.
That choice is intentional and central to the project's consistency model.

## Possible next steps

For a production deployment, useful follow-ups would include CI checks,
structured request/correlation IDs, rate limiting on authentication
endpoints, operational metrics, backups and restore drills, and testing
concurrency against the chosen production database. Any production
rollout should also review token transport/storage, secret rotation,
database permissions, and deployment-specific CORS settings.
