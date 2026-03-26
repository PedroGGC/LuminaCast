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
from app.seed import seed_database, auto_seed_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables & seed
    Base.metadata.create_all(bind=engine)
    init_db()
    seed_database()

    # Auto-seed em background (se banco vazio)
    asyncio.create_task(auto_seed_database())

    yield


app = FastAPI(title="LuminaCast API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
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


@app.get("/")
async def root():
    return {"status": "ok", "message": "LuminaCast API is running 🚀"}
