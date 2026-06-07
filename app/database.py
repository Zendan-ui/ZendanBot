import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, future=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


def _sqla_type_to_sql(col) -> str:
    """Best-effort SQL type for SQLite ALTER TABLE ADD COLUMN."""
    t = col.type.__class__.__name__.lower()
    if "int" in t or "biginteger" in t:
        return "INTEGER"
    if "bool" in t:
        return "BOOLEAN"
    if "datetime" in t:
        return "DATETIME"
    return "TEXT"


async def _auto_migrate(conn) -> None:
    """Add columns that exist on the models but not yet in the SQLite tables.

    This lets us add new features/fields without dropping the database.
    Only runs for SQLite (the default). For Postgres use Alembic in production.
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    for table in Base.metadata.sorted_tables:
        rows = (await conn.execute(text(f'PRAGMA table_info("{table.name}")'))).fetchall()
        if not rows:
            continue  # table will be created by create_all
        existing = {r[1] for r in rows}
        for col in table.columns:
            if col.name not in existing:
                sql_type = _sqla_type_to_sql(col)
                default = ""
                # only apply simple literal python defaults; skip SQL functions
                # (e.g. func.now()) and callables which aren't valid in ALTER TABLE.
                arg = getattr(col.default, "arg", None) if col.default is not None else None
                if isinstance(arg, bool):
                    default = f" DEFAULT {1 if arg else 0}"
                elif isinstance(arg, (int, float)):
                    default = f" DEFAULT {arg}"
                elif isinstance(arg, str):
                    safe = arg.replace("'", "''")
                    default = f" DEFAULT '{safe}'"
                await conn.execute(text(
                    f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {sql_type}{default}'
                ))
                logger.info("auto-migrate: added %s.%s", table.name, col.name)


async def init_db() -> None:
    # import models so all tables are registered on Base.metadata
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _auto_migrate(conn)


async def execute_raw(query: str, params: dict | None = None):
    async with async_session() as session:
        result = await session.execute(text(query), params or {})
        await session.commit()
        return result
