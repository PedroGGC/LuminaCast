import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/luminacast.db")

# Detectar tipo de banco
is_sqlite = "sqlite" in DATABASE_URL
is_postgres = "postgres" in DATABASE_URL

# Configurações específicas
engine_kwargs = {"echo": False}

if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}

# Criar engine
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Generator de sessão síncrona."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Inicializa o banco, criando tabelas se necessário."""
    from app import models

    Base.metadata.create_all(bind=engine)

    if not is_sqlite:
        return

    from sqlalchemy import inspect

    inspector = inspect(engine)

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
