from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped session and transaction.

    All activities involved in a request are treated as a single transaction
    such that if any operation fails, all prior ones within the request are
    rolled back, therefore ensuring ATOMICITY.
    """
    async with SessionFactory() as session:
        async with session.begin():
            yield session
