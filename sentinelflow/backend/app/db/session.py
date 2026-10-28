from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.config import get_settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

settings = get_settings()
_engine_kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True}
if not settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs.update(
        {
            "pool_size": 20,
            "max_overflow": 30,
            "pool_timeout": 30,
        }
    )
engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
