# Clinic Booking API

A clinic appointment booking API built with **FastAPI**, **SQLAlchemy**'s
async ORM, and **Alembic**. It supports patient authentication, doctor
discovery, availability lookup, and appointment booking, cancellation,
and rescheduling.

I wanted this to be more than an API where the endpoints simply work. I
organized the implementation around clear module boundaries, request-level
transaction consistency, and database constraints that help protect booking
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
- [Docker image](#docker-image)
- [License](#license)

## Why this stack

I chose **FastAPI** because of its lightweight ASGI foundation, native
support for asynchronous request handling, and automatic OpenAPI
documentation. It works naturally with async database
connections, and makes it possible to choose any ORM
without tightly coupling the application to the framework.

Django and Go are both strong options, depending on the context. Django
is particularly useful when a project benefits from its integrated ORM,
admin, and broader batteries-included conventions. Go is a strong choice
for teams that want a compiled language, straightforward deployment, and
efficient concurrency. For this assessment, I found that FastAPI offered a
practical balance of development speed, async support, low framework
overhead, and architectural flexibility.

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
- Automated asynchronous API tests that can be run with pytest.
- Docker configuration and CI/CD that build and publish a container image for consistent deployments.

## Architecture

I organized the codebase around a **layered, modular design**. Each feature
is grouped by domain, while responsibilities remain separated within that
feature.

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

I find this separation makes the code easier to locate and test. It also
gives the project room to grow without concentrating all the logic in route
handlers or one large service.

## Key engineering decisions

### One transaction per request

The database dependency opens a session and transaction for the request.
Routes and services share that session instead of starting and
committing independent transactions inside each service method.

I chose this because a request may need to coordinate more than one
service operation. If each operation is committed independently, an
operation might remain committed even if a another one failed. A
request-level transaction keeps those database changes atomic such
that successful requests commit, while an exception causes the
transaction to roll back.

Services can flush when they need the database to evaluate pending
changes or constraints, but they do not independently decide the
request's commit boundary.

### Database constraints protect booking integrity

The API validates each requested slot against the doctor's working hours, the
one-hour advance-booking cutoff, and existing appointments. The database
adds a partial unique index for a doctor's booked appointment start time,
along with checks on appointment status and start/end ordering.

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

The API calculates availability from each doctor's configured working hours and
existing booked appointments. The logic creates 30-minute slots on the
clinic clock, converts slot times to UTC for comparisons and API output,
excludes already-booked slots, and omits slots that begin within the
one-hour booking cutoff.

The clinic time zone is configurable and has a default value of `Africa/Nairobi`.
Keeping the clinic's local schedule separate from UTC timestamps. This avoids
treating a clinic's opening hours as if they were UTC hours.

### Annotated dependencies reduce repetition

I exposed common dependencies, such as the current authenticated patient
and database session, as annotated types. This keeps route dependency
injection concise while leaving authentication and session lifecycle
defined centrally.

### Centralized exception handling

I handled expected domain errors through a common base class at the
application level. Database integrity and SQLAlchemy errors also have
centralized handlers. This keeps the routes focused on the request instead
of repeating `try/except` blocks and response formatting, and gives clients
a consistent error structure.

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

Keep `DEBUG=false` in production and configure `CORS_ORIGINS` for the
exact browser origins that should be allowed. For PostgreSQL, use the
async SQLAlchemy URL form, for example
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

I configured the tests to use an isolated async SQLite database by default
(`test_clinic.db`) and to override the application's database dependency.
You can set `TEST_DATABASE_URL` to point the tests at another suitable test
database. **Do not point tests at a database containing data you need to keep**
because the test suite drops and recreates the tables.

## Configuration

---

| Variable                        | Purpose                                                           | Default              |
| ------------------------------- | ----------------------------------------------------------------- | -------------------- |
| `APP_NAME`                      | API title                                                         | `Clinic Booking API` |
| `APP_ENV`                       | Environment label                                                 | `development`        |
| `DEBUG`                         | Enables debug logging and more diagnostic database error messages | `false`              |
| `DATABASE_URL`                  | SQLAlchemy async database URL                                     | Required             |
| `SECRET_KEY`                    | Secret used to sign access tokens                                 | Required             |
| `ALGORITHM`                     | JWT signing algorithm                                             | `HS256`              |
| `ACCESS_TOKEN_LIFETIME_MINUTES` | Access-token lifetime                                             | `30`                 |
| `REFRESH_TOKEN_LIFETIME_DAYS`   | Refresh-token lifetime                                            | `7`                  |
| `TIMEZONE`                      | IANA clinic time zone                                             | `Africa/Nairobi`     |
| `CORS_ORIGINS`                  | Allowed browser origins                                           | `[]`                 |

---

The settings class validates the configured time zone and constrains
token lifetimes to reasonable ranges.

## API reference

All versioned endpoints are under `/api/v1`. The running OpenAPI
document at `/openapi.json` and Swagger UI at `/docs` are the definitive
interactive reference.

### Operations

| Method | Endpoint  | Purpose                       | Auth |
| ------ | --------- | ----------------------------- | ---- |
| `GET`  | `/health` | Health check                  | No   |
| `GET`  | `/docs`   | API information and Docs path | No   |

### Authentication

| Method | Endpoint                | Purpose                                     | Auth                |
| ------ | ----------------------- | ------------------------------------------- | ------------------- |
| `POST` | `/api/v1/auth/register` | Register a patient and issue tokens         | No                  |
| `POST` | `/api/v1/auth/login`    | Authenticate with email and password        | No                  |
| `POST` | `/api/v1/auth/refresh`  | Rotate a refresh token and issue new tokens | No                  |
| `POST` | `/api/v1/auth/logout`   | Revoke a refresh token                      | No                  |
| `GET`  | `/api/v1/auth/me`       | Get the authenticated patient               | Bearer access token |

Example registration request:

```json
{
  "full_name": "Alex Mwangi",
  "email": "alex@example.com",
  "password": "choose-a-strong-password",
  "phone": "0712345678"
}
```

The phone field is optional. The response includes an `access_token` and a `refresh_token`.

To test protected endpoints in Swagger UI:

1. Open `/docs` and register or log in using the authentication endpoints.
2. Copy the `access_token` value from the response (not the refresh token).
3. Click **Authorize** near the top of the Swagger page.
4. Paste the access token into the HTTP Bearer value field. Enter the token itself; Swagger UI adds the `Bearer` prefix.
5. Click **Authorize**, close the dialog, and try an endpoint marked as requiring a bearer access token.

Access tokens are short-lived. Use the refresh endpoint with the refresh token to obtain a new token pair. Keep the refresh token secure and use it only with the refresh and logout endpoints.

### Doctors and availability

| Method | Endpoint                                                   | Purpose                                                | Auth |
| ------ | ---------------------------------------------------------- | ------------------------------------------------------ | ---- |
| `GET`  | `/api/v1/doctors`                                          | List active doctors                                    | No   |
| `GET`  | `/api/v1/doctors/{doctor_id}`                              | Get an active doctor                                   | No   |
| `GET`  | `/api/v1/doctors/{doctor_id}/availability?date=YYYY-MM-DD` | List available 30-minute slots for a clinic-local date | No   |

Example:

```bash
curl "http://127.0.0.1:8000/api/v1/doctors/DOCTOR_UUID/availability?date=2026-10-22"
```

Availability returns a list of `starts_at` and `ends_at` timestamps.
Timestamps are returned in UTC; the `date` query parameter represents a
date in the clinic's configured time zone.

### Appointments

All appointment endpoints require a valid bearer access token and operate on the authenticated patient's own appointments.

| Method  | Endpoint                                                   | Purpose                                       | Auth                |
| ------- | ---------------------------------------------------------- | --------------------------------------------- | ------------------- |
| `POST`  | `/api/v1/appointments`                                     | Book an appointment                           | Bearer access token |
| `GET`   | `/api/v1/appointments/{appointment_id}`                    | Retrieve one of the patient's appointments    | Bearer access token |
| `PATCH` | `/api/v1/appointments/{appointment_id}/cancel`             | Cancel an appointment                         | Bearer access token |
| `PATCH` | `/api/v1/appointments/{appointment_id}/reschedule`         | Reschedule an appointment                     | Bearer access token |
| `GET`   | `/api/v1/patients/{patient_id}/appointments?upcoming=true` | List the authenticated patient's appointments | Bearer access token |

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

I used AI as a development aid, not as a substitute for my own engineering
judgment. It was particularly useful to me in three areas:

- **Exception handling:** AI helped me think through a global
  exception-handling convention that is registered on the FastAPI application.
  This replaced repeated error-handling boilerplate with a consistent
  response schema.
- **Availability logic:** AI also helped me explore how to generate and
  filter 30-minute availability slots and handle UTC conversion.
- **Seed data and tests:** AI helped speed up work on sample data and
  automated tests.

I reviewed the suggestions and made the architectural decisions based on
the requirements. One point where I took a different approach was
**transaction ownership**. AI suggested that service methods manage their
own transactions. I chose request-scoped transaction ownership instead,
so a single request has one atomic transaction even when a route runs
multiple service operations. That was a deliberate decision to keep the
data consistent.

## Docker configuration

I included Docker configuration and CI/CD to build and publish a
container image. Using the published image gives development, testing, and
deployment environments the same dependencies, reducing differences caused
by local setup. The CI workflow rebuilds and publishes the image when its
configured trigger runs. When deploying, use the image reference published
by the repository's workflow. Keep environment-specific settings such as
`DATABASE_URL` and `SECRET_KEY` outside the image and provide them at runtime.

## Production database setup

For production, I ran database migrations and seed data deliberately rather
than having them run automatically when the API starts. Both utilities ask
for the database URL in the terminal, so I do not need to put it in the
Docker image.

### Applying online migrations

After checking out the version of the code I intended to deploy, I ran the
migration utility from the project root:

```bash
poetry run python -m scripts.production_migrate
```

Enter the PostgreSQL URL for the production database when prompted, then check
the displayed host and database name. Type `MIGRATE` to apply the pending
Alembic migrations. The utility runs `alembic upgrade head` against that database
and does not deploy or restart the API.

The script accepts `postgresql://` and `postgresql+asyncpg://` URLs. It uses the
async PostgreSQL driver configured by the application. The database must accept
connections from the machine running the command. Depending on the provider, that
may require IP allowlisting or SSL configuration.

Review pending migration files and back up important production data before
applying schema changes. Run migrations using the same code revision that you
plan to deploy.

### Seeding production data

One can initialize production seed data separately:

```bash
poetry run python -m scripts.production_seed
```

Enter the target PostgreSQL URL and type `SEED` after checking the displayed
host and database name. The utility reuses the project's existing seed logic
instead of maintaining a second copy of the doctor and working-hour definitions.

The seed data adds sample doctors with weekday working hours from 09:00 to
13:00 and 14:00 to 17:00 in the clinic's configured time zone. The seed logic
preserves existing weekday schedules.

One must apply migrations before seeding. Production seeding is an explicit
initialization step, not something that should run automatically whenever
the API starts. They must also keep database credentials out of source control
and never include them into the Docker image.

## License

I have licensed this project under the **BSD 3-Clause License**. The full
license terms are available in the [`LICENSE`](LICENSE) file in the root
directory of this repository. If you use or fork this project, please read
the license and follow its terms.
