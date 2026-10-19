"""Run the initial seed against an explicitly supplied production database.

Usage:
    poetry run python -m scripts.production_seed

The database URL is entered interactively so it is not echoed to the terminal or
stored in shell history. The URL overrides DATABASE_URL for this process only.
"""

import asyncio
import os
import secrets
from getpass import getpass

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


def _parse_database_url(raw_url: str) -> URL:
    """Validate and normalize a PostgreSQL URL for SQLAlchemy's async driver."""
    try:
        url = make_url(raw_url.strip())
    except (ArgumentError, ValueError) as exc:
        raise ValueError(
            "That does not look like a valid SQLAlchemy database URL."
        ) from exc

    # Accept the common provider URL forms, but use the async driver required by
    # this application. Preserve credentials and query parameters when normalizing.
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+asyncpg")

    if url.drivername != "postgresql+asyncpg":
        raise ValueError(
            "Expected a PostgreSQL URL (postgresql:// or postgresql+asyncpg://)."
        )
    if not url.host or not url.database:
        raise ValueError("The database URL must include a host and database name.")

    return url


def _configure_process(url: URL) -> None:
    """Set settings before importing the application, which creates its engine."""
    os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)
    # This is a standalone data-initialization process, not an API server. Avoid
    # SQL debug logging and make the utility independent of the app's secret key.
    os.environ["DEBUG"] = "false"
    os.environ["APP_ENV"] = "production"
    os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(32))


def _describe_target(url: URL) -> str:
    """Return a safe target description without credentials or query parameters."""
    return f"host: {url.host}\ndatabase: {url.database}"


async def _run_seed() -> None:
    # Import only after DATABASE_URL and the other required settings are supplied.
    # Importing scripts.seed imports core.database, which creates the engine.
    from scripts.seed import seed

    await seed()


def main() -> None:
    print("Production database seeding")
    print("Enter the PostgreSQL URL for the database you intend to initialize.")
    raw_url = getpass("Database URL (input hidden): ").strip()
    if not raw_url:
        raise SystemExit("No database URL supplied; nothing was changed.")

    try:
        url = _parse_database_url(raw_url)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    print("\nTarget database:")
    print(_describe_target(url))
    print(
        "\nThis runs the existing seed logic. Existing doctor records are reused, "
        "and existing weekday schedules are left unchanged."
    )
    confirmation = input("Type SEED to continue: ").strip()
    if confirmation != "SEED":
        print("Cancelled; no seed operation was started.")
        return

    _configure_process(url)
    try:
        asyncio.run(_run_seed())
    except Exception:
        print("\nSeeding failed. The seed transaction should have been rolled back.")
        raise
    else:
        print("\nSeeding completed successfully.")


if __name__ == "__main__":
    main()
