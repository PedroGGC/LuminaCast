import os
import asyncio
from dotenv import load_dotenv

load_dotenv()  # Carrega variáveis do .env

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine, init_db
from app.routes.catalog import router as catalog_router
from app.routes.auth import router as auth_router
from app.routes.user_list import router as user_list_router
from app.routes.media import router as media_router
from app.routes.sync import router as sync_router
from app.routes.home import router as home_router
from app.seed import seed_database, auto_seed_database, get_latest_release_tag
from app.routes.history import router as history_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create tables & seed
    Base.metadata.create_all(bind=engine)
    init_db()

    # Verifica se o banco offline está atualizado
    try:
        from pathlib import Path

        version_file = Path("data/.offline-db-version")
        current_version = (
            version_file.read_text().strip() if version_file.exists() else None
        )
        latest_version = get_latest_release_tag()

        if latest_version and current_version != latest_version:
            print(f"\n{'=' * 60}")
            print(f"  Banco offline desatualizado!")
            print(f"  Versão atual: {current_version or 'nenhuma'}")
            print(f"  Versão disponível: {latest_version}")
            print(f"\n  Para atualizar, rode:")
            print(f"  cd backend && .\\venv\\Scripts\\python.exe app/seed.py")
            print(f"{'=' * 60}\n")
    except Exception:
        pass

    seed_database()

    # Auto-seed em background (se banco vazio)
    asyncio.create_task(auto_seed_database())

    yield


from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from app.limiter import limiter

app = FastAPI(title="LuminaCast API", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "https://lumina-cast.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog_router)
app.include_router(auth_router)
app.include_router(user_list_router)
app.include_router(media_router)
app.include_router(sync_router)
app.include_router(home_router)
app.include_router(history_router)


@app.get("/")
async def root():
    return {"status": "ok", "message": "LuminaCast API is running 🚀"}
