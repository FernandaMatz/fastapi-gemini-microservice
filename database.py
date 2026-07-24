import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config import settings

logger = logging.getLogger(__name__)

# Normaliza a URL do banco para suporte assíncrono (Asyncpg) em provedores de nuvem (Render, Koyeb, Neon, Supabase)
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Configurações do engine assíncrono
engine_kwargs = {"echo": False, "future": True}
if db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(db_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Injeta a sessão do banco de dados para endpoints assíncronos."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error("Erro na sessão do banco de dados, realizando rollback: %s", str(exc), exc_info=True)
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Cria as tabelas no banco de dados se não existirem."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Estrutura do banco de dados sincronizada com sucesso.")
