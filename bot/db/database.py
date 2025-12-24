"""Async SQLAlchemy database configuration."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine
from sqlalchemy.orm import DeclarativeBase

from bot.config import config


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Engine and session maker will be initialized lazily
_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    """Get or create the async database engine."""
    global _engine
    if _engine is None:
        if not config.database_url:
            raise ValueError("DATABASE_URL is not configured")
        _engine = create_async_engine(
            config.database_url,
            echo=False,
            pool_pre_ping=True,
        )
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session maker."""
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_maker


# Aliases for backward compatibility
@property
def engine() -> AsyncEngine:
    return get_engine()


@property
def async_session_maker() -> async_sessionmaker[AsyncSession]:
    return get_session_maker()


async def get_session() -> AsyncSession:
    """Get a new async database session."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session


async def init_db() -> None:
    """Initialize database tables."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    global _engine, _async_session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None
