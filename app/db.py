from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

try:  # pragma: no cover - dependency presence varies by environment
    import asyncpg  # type: ignore
except ImportError:  # pragma: no cover - handled at runtime
    asyncpg = None  # type: ignore


class DatabaseUnavailable(RuntimeError):
    pass


@dataclass(slots=True)
class DatabaseTransaction:
    pool: Any
    connection: Any | None = None
    _tx: Any | None = None

    async def start(self) -> 'DatabaseTransaction':
        if self.pool is None:
            raise DatabaseUnavailable('Database pool is not initialized')
        self.connection = await self.pool.acquire()
        self._tx = self.connection.transaction()
        await self._tx.start()
        return self

    async def commit(self) -> None:
        if self._tx is not None:
            await self._tx.commit()
        if self.connection is not None:
            await self.pool.release(self.connection)
            self.connection = None
            self._tx = None

    async def rollback(self) -> None:
        if self._tx is not None:
            await self._tx.rollback()
        if self.connection is not None:
            await self.pool.release(self.connection)
            self.connection = None
            self._tx = None


class Database:
    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 10) -> None:
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self.pool: Any | None = None
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None

    async def connect(self) -> None:
        if not self.dsn:
            raise DatabaseUnavailable('DATABASE_URL is not configured')
        if asyncpg is None:
            raise DatabaseUnavailable('asyncpg is required to connect to PostgreSQL')
        self.pool = await asyncpg.create_pool(  # type: ignore[attr-defined]
            dsn=self.dsn,
            min_size=self.min_size,
            max_size=self.max_size,
            command_timeout=60,
            server_settings={'search_path': 'hrms,public'},
        )
        sqlalchemy_dsn = self.dsn.replace('postgresql://', 'postgresql+asyncpg://', 1)
        self.engine = create_async_engine(sqlalchemy_dsn, future=True, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False, autoflush=False)

    async def close(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    def acquire(self) -> Any:
        if self.pool is None:
            raise DatabaseUnavailable('Database pool is not initialized')
        return self.pool.acquire()

    async def transaction(self) -> DatabaseTransaction:
        return await DatabaseTransaction(self.pool).start()

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        if self.pool is None:
            raise DatabaseUnavailable('Database pool is not initialized')
        return await self.pool.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Any | None:
        if self.pool is None:
            raise DatabaseUnavailable('Database pool is not initialized')
        return await self.pool.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        if self.pool is None:
            raise DatabaseUnavailable('Database pool is not initialized')
        return await self.pool.fetchval(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        if self.pool is None:
            raise DatabaseUnavailable('Database pool is not initialized')
        return await self.pool.execute(query, *args)

    def session(self) -> AsyncSession:
        if self.session_factory is None:
            raise DatabaseUnavailable('SQLAlchemy session factory is not initialized')
        return self.session_factory()

    async def executemany(self, query: str, args_list: list[tuple[Any, ...]]) -> None:
        if self.pool is None:
            raise DatabaseUnavailable('Database pool is not initialized')
        async with self.pool.acquire() as conn:
            await conn.executemany(query, args_list)
