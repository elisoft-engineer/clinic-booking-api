"""Apply pending Alembic migrations to an explicitly selected production database.

Run from the project root:
    poetry run python -m scripts.production_migrate

The database URL is requested interactively so it is not echoed to the terminal
or added to shell history. It overrides DATABASE_URL for the migration process only.
"""

import os
import secrets
import subprocess
import sys
from getpass import getpass

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


def parse_database_url(raw_url: str) -> URL:
    """Validate and normalize a PostgreSQL URL for the async application."""
    try:
        url = make_url(raw_url.strip())
    except (ArgumentError, ValueError) as exc:
        raise ValueError(
            "That does not look like a valid SQLAlchemy database URL."
        ) from exc

    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+asyncpg")

    if url.drivername != "postgresql+asyncpg":
        raise ValueError(
            "Expected a PostgreSQL URL (postgresql:// or postgresql+asyncpg://)."
        )
    if not url.host or not url.database:
        raise ValueError("The database URL must include a host and database name.")

    return url


def main() -> int:
    print("Production database migrations")
    print("Enter the PostgreSQL URL for the database you intend to migrate.")
    raw_url = getpass("Database URL (input hidden): ").strip()
    if not raw_url:
        print("No database URL supplied; nothing was changed.")
        return 1

    try:
        url = parse_database_url(raw_url)
    except ValueError as exc:
        print(f"Invalid database URL: {exc}")
        return 1

    print("\nTarget database:")
    print(f"host: {url.host}")
    print(f"database: {url.database}")
    print("\nThis will apply all pending Alembic migrations to that database.")
    if input("Type MIGRATE to continue: ").strip() != "MIGRATE":
        print("Cancelled; no migration was started.")
        return 0

    # Set configuration before Alembic imports migrations/env.py and the app settings.
    env = os.environ.copy()
    env["DATABASE_URL"] = url.render_as_string(hide_password=False)
    env["APP_ENV"] = "production"
    env["DEBUG"] = "false"
    # Settings require a secret key even though migrations do not use authentication.
    # A process-local value avoids requiring or printing an unrelated production secret.
    env.setdefault("SECRET_KEY", secrets.token_urlsafe(32))

    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=env,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print("\nMigration command failed. Check the error above before retrying.")
        return exc.returncode or 1

    print("\nMigrations completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
