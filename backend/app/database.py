import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/luminacast.db")

# Converte postgres:// para asyncpg (necessário para asyncpg)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Configurações específicas para cada banco
engine_kwargs = {"echo": False}

if "sqlite" in DATABASE_URL:
    engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
elif "asyncpg" in DATABASE_URL:
    # asyncpg não precisa de connect_args especiais
    pass

# Engine para operações síncronas
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Engine async (se precisar no futuro)
async_engine = create_async_engine(
    DATABASE_URL.replace("postgresql+asyncpg", "postgresql"), echo=False
)
AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


def get_db():
    """Generator de sessão síncrona (padrão para FastAPI)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_db_async():
    """Generator de sessão assíncrona (para rotas async)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def init_db():
    """Inicializa o banco, criando tabelas faltantes se necessário."""
    from app import models
    from sqlalchemy import inspect

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)

    # Migra colunas faltantes na tabela `media`
    media_cols = [c["name"] for c in inspector.get_columns("media")]

    missing_media = {
        "backdrop_url": "VARCHAR(500)",
        "last_verified": "VARCHAR(50)",
        "available": "BOOLEAN DEFAULT 1",
    }
    for col, col_type in missing_media.items():
        if col not in media_cols:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE media ADD COLUMN {col} {col_type}"))
                conn.commit()
            print(f"[DB] Coluna '{col}' adicionada à tabela media")
