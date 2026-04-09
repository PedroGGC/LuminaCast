import asyncio
import os
import time
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.utils.filters import is_japanese_content
from app.database import get_db, SessionLocal
from app.models import Media

router = APIRouter(prefix="/api", tags=["home"])


# ─── In-memory cache (TTL: 20 min) ───────────────────────────────────────────

_cache: dict = {"data": None, "timestamp": 0}
CACHE_TTL = 20 * 60


def _is_cache_valid() -> bool:
    return (
        _cache["data"] is not None and (time.time() - _cache["timestamp"]) < CACHE_TTL
    )


def _set_cache(data: dict) -> None:
    _cache["data"] = data
    _cache["timestamp"] = time.time()


# ─── Carousel fetchers ───────────────────────────────────────────────────────


async def _get_season_now() -> list:
    """Lançamentos da Temporada (Jikan)."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://api.jikan.moe/v4/seasons/now?limit=15")
            if resp.status_code == 200:
                return [
                    {
                        "id": f"mal_{item.get('mal_id')}",
                        "mal_id": item.get("mal_id"),
                        "title": item.get("title"),
                        "poster_url": item.get("images", {})
                        .get("jpg", {})
                        .get("large_image_url"),
                        "score": item.get("score"),
                        "year": item.get("year"),
                        "season": item.get("season"),
                    }
                    for item in resp.json().get("data", [])[:15]
                ]
    except Exception as e:
        print(f"[Home] Erro season_now: {e}")
    return []


async def _get_top_anime() -> list:
    """Em Alta — Animes Populares (Jikan)."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.jikan.moe/v4/top/anime?filter=bypopularity&limit=15"
            )
            if resp.status_code == 200:
                return [
                    {
                        "id": f"mal_{item.get('mal_id')}",
                        "mal_id": item.get("mal_id"),
                        "title": item.get("title"),
                        "poster_url": item.get("images", {})
                        .get("jpg", {})
                        .get("large_image_url"),
                        "score": item.get("score"),
                    }
                    for item in resp.json().get("data", [])[:15]
                ]
    except Exception as e:
        print(f"[Home] Erro top_anime: {e}")
    return []


async def _get_western_cartoons() -> list:
    """Desenhos Populares — TMDB, sem conteúdo de origem japonesa."""
    tmdb_key = os.getenv("TMDB_API_KEY")
    if not tmdb_key:
        return []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.themoviedb.org/3/discover/tv",
                params={
                    "api_key": tmdb_key,
                    "with_genres": 16,
                    "without_original_language": "ja",
                    "sort_by": "popularity.desc",
                    "language": "pt-BR",
                    "page": 1,
                },
            )
            if resp.status_code == 200:
                filtered = [
                    item
                    for item in resp.json().get("results", [])
                    if not is_japanese_content(item)
                ]
                return [
                    {
                        "id": f"tmdb_{item.get('id')}",
                        "tmdb_id": item.get("id"),
                        "title": item.get("name"),
                        "poster_url": f"https://image.tmdb.org/t/p/w500{item['poster_path']}"
                        if item.get("poster_path")
                        else None,
                        "score": item.get("vote_average"),
                        "year": item.get("first_air_date", "")[:4] or None,
                    }
                    for item in filtered[:15]
                ]
    except Exception as e:
        print(f"[Home] Erro western_cartoons: {e}")
    return []


# ─── Task 4: Lazy Revalidation ───────────────────────────────────────────────

_REVALIDATION_THRESHOLD_DAYS = 30


async def _revalidate_home_items(carousels: list) -> None:
    """
    Verifica em background se os itens da home ainda estão disponíveis.
    Atualiza `last_verified` e `available` no banco quando passam 30 dias.
    Roda de forma não-bloqueante (background task).
    """
    from app.database import SessionLocal
    from app.models import Media
    from app.services.scraper import resolve_provider_slug

    threshold = datetime.utcnow() - timedelta(days=_REVALIDATION_THRESHOLD_DAYS)

    db = SessionLocal()
    try:
        for carousel in carousels:
            if carousel.get("type") != "anime":
                continue
            for item in carousel.get("items", []):
                mal_id = item.get("mal_id")
                if not mal_id:
                    continue

                external_id = str(mal_id)
                media = db.query(Media).filter(Media.external_id == external_id).first()

                needs_check = True
                if media and media.last_verified:
                    try:
                        last_verified_dt = datetime.fromisoformat(media.last_verified)
                        needs_check = last_verified_dt < threshold
                    except Exception:
                        pass

                if not needs_check:
                    continue

                try:
                    slug = await resolve_provider_slug(mal_id)
                    is_available = slug is not None
                except Exception:
                    is_available = False

                now_iso = datetime.utcnow().isoformat()
                if media:
                    media.last_verified = now_iso
                    media.available = is_available
                    db.commit()
                    print(f"[Home Lazy] MAL {mal_id} — disponível={is_available}")
    except Exception as e:
        print(f"[Home Lazy Revalidation] Erro: {e}")
    finally:
        db.close()


@router.get("/home")
async def get_home(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Home Page com carrosséis dinâmicos.
    Cache em memória (TTL: 20 min). Revalidação lazy de disponibilidade em background.
    """
    if _is_cache_valid():
        # Usar asyncio.create_task para rodar em background (sem bloquear)
        asyncio.create_task(_revalidate_home_items(_cache["data"]["carousels"]))
        return _cache["data"]

    season_now, top_anime, cartoons = await asyncio.gather(
        _get_season_now(),
        _get_top_anime(),
        _get_western_cartoons(),
    )

    # Recuperar IDs para verificar se estão marcados como indisponíveis
    mal_ids = [
        str(item["mal_id"]) for item in season_now + top_anime if item.get("mal_id")
    ]

    unavailable_ids = set()
    if mal_ids:
        unavailable_media = (
            db.query(Media.external_id)
            .filter(
                Media.media_type == "anime",
                Media.external_id.in_(mal_ids),
                Media.available == False,
            )
            .all()
        )
        for m in unavailable_media:
            unavailable_ids.add(m[0])

    # Filtrar animes indisponíveis (Task 1/4 - Otimização de carrossel)
    season_now = [it for it in season_now if str(it["mal_id"]) not in unavailable_ids]
    top_anime = [it for it in top_anime if str(it["mal_id"]) not in unavailable_ids]

    response = {
        "carousels": [
            {"title": "Lançamentos da Temporada", "type": "anime", "items": season_now},
            {"title": "Em Alta", "type": "anime", "items": top_anime},
            {"title": "Desenhos Populares", "type": "desenho", "items": cartoons},
        ]
    }

    _set_cache(response)

    # Usar asyncio.create_task para rodar em background (sem bloquear)
    asyncio.create_task(_revalidate_home_items(response["carousels"]))

    return response


@router.get("/home/refresh")
async def refresh_home(background_tasks: BackgroundTasks):
    """Força refresh do cache da home page."""
    global _cache
    _cache = {"data": None, "timestamp": 0}
    return await get_home(background_tasks)
