from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Media
from app.services.sync_service import sync_media_by_id
import os
import httpx
import asyncio

router = APIRouter(prefix="/api/sync-media", tags=["sync"])

TMDB_BASE = "https://api.themoviedb.org/3"

@router.post("")
async def sync_media_db(db: Session = Depends(get_db)):
    tmdb_key = os.getenv("TMDB_API_KEY", "").strip()
    if not tmdb_key:
        raise HTTPException(status_code=500, detail="TMDB_API_KEY não configurada.")

    # Limpa banco opcionalmente ou mantém (conforme instrução anterior de evitar duplicatas)
    # db.query(Media).delete() 
    # db.commit()

    CARTOON_TITLES = [
        "Adventure Time", "Regular Show", "SpongeBob", "Gravity Falls", 
        "Ben 10", "Teen Titans", "Steven Universe", "The Owl House",
        "The Amazing Digital Circus", "Courage the Cowardly Dog",
        "Dexter's Laboratory", "Avatar: The Last Airbender",
        "Rick and Morty", "Samurai Jack",
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        params_base = {"api_key": tmdb_key, "language": "pt-BR"}

        # ─── ANIMES ──────────────────
        anime_params = {**params_base, "with_genres": "16", "with_original_language": "ja", "sort_by": "popularity.desc"}
        resp = await client.get(f"{TMDB_BASE}/discover/tv", params=anime_params)
        if resp.status_code == 200:
            animes = resp.json().get("results", [])[:15]
            for show in animes:
                await sync_media_by_id(str(show["id"]), "anime", db)
                await asyncio.sleep(0.5)

        # ─── DESENHOS ──────────────────
        for title in CARTOON_TITLES:
            print(f"[TMDB LOG] Buscando título '{title}'")
            search_resp = await client.get(f"{TMDB_BASE}/search/tv", params={**params_base, "query": title})
            if search_resp.status_code == 200:
                results = search_resp.json().get("results", [])
                if results:
                    await sync_media_by_id(str(results[0]["id"]), "desenho", db)
            await asyncio.sleep(0.5)

    return {"message": "Sincronização concluída com sucesso!"}
