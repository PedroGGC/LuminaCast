import asyncio
import os
import time

import httpx
from fastapi import APIRouter

from app.utils.filters import is_japanese_content

router = APIRouter(prefix="/api", tags=["home"])

# ─── In-memory cache (TTL: 20 min) ───────────────────────────────────────────

_cache: dict = {"data": None, "timestamp": 0}
CACHE_TTL = 20 * 60


def _is_cache_valid() -> bool:
    return _cache["data"] is not None and (time.time() - _cache["timestamp"]) < CACHE_TTL


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
                        "poster_url": item.get("images", {}).get("jpg", {}).get("large_image_url"),
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
                        "poster_url": item.get("images", {}).get("jpg", {}).get("large_image_url"),
                        "score": item.get("score"),
                    }
                    for item in resp.json().get("data", [])[:15]
                ]
    except Exception as e:
        print(f"[Home] Erro top_anime: {e}")
    return []


async def _get_movies() -> list:
    """Filmes de Anime (Jikan)."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.jikan.moe/v4/top/anime?type=movie&limit=15"
            )
            if resp.status_code == 200:
                return [
                    {
                        "id": f"mal_{item.get('mal_id')}",
                        "mal_id": item.get("mal_id"),
                        "title": item.get("title"),
                        "poster_url": item.get("images", {}).get("jpg", {}).get("large_image_url"),
                        "score": item.get("score"),
                        "year": item.get("year"),
                    }
                    for item in resp.json().get("data", [])[:15]
                ]
    except Exception as e:
        print(f"[Home] Erro movies: {e}")
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
                    item for item in resp.json().get("results", [])
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


# ─── Routes ───────────────────────────────────────────────────────────────────


@router.get("/home")
async def get_home():
    """
    Home Page com carrosséis dinâmicos.
    Usa cache em memória (TTL: 20 min) e busca os 4 carrosséis em paralelo.
    """
    if _is_cache_valid():
        return _cache["data"]

    season_now, top_anime, movies, cartoons = await asyncio.gather(
        _get_season_now(),
        _get_top_anime(),
        _get_movies(),
        _get_western_cartoons(),
    )

    response = {
        "carousels": [
            {"title": "Lançamentos da Temporada", "type": "anime", "items": season_now},
            {"title": "Em Alta", "type": "anime", "items": top_anime},
            {"title": "Filmes de Anime", "type": "anime", "items": movies},
            {"title": "Desenhos Populares", "type": "desenho", "items": cartoons},
        ]
    }

    _set_cache(response)
    return response


@router.get("/home/refresh")
async def refresh_home():
    """Força refresh do cache da home page."""
    global _cache
    _cache = {"data": None, "timestamp": 0}
    return await get_home()
