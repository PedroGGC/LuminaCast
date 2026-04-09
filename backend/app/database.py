import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/luminacast.db")

engine_kwargs = {}
if "sqlite" in DATABASE_URL:
    engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}

engine = create_engine(DATABASE_URL, echo=False, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db():
    """Inicializa o banco, criando colunas/tabelas faltantes se necessário."""
    from app import models
    from sqlalchemy import inspect

    # --- Cria tabelas novas
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)

    # --- Migra colunas faltantes na tabela `media` ---
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



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
