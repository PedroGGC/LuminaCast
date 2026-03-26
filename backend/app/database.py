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
    """Inicializa o banco, criando colunas faltantes se necessário."""
    from app.models import Media
    from sqlalchemy import inspect

    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("media")]

    if "backdrop_url" not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE media ADD COLUMN backdrop_url VARCHAR(500)"))
            conn.commit()
        print("[DB] Coluna backdrop_url adicionada à tabela media")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
