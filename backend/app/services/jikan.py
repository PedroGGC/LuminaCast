import httpx
import asyncio
import json
import time
from datetime import datetime
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.models import JikanCache
from app.database import SessionLocal

JIKAN_BASE_URL = "https://api.jikan.moe/v4"
RATE_LIMIT_DELAY = 1.0


def _is_valid_mal_id(mal_id: int) -> bool:
    if mal_id is None:
        return False
    try:
        return 0 < int(mal_id) < 100_000
    except (ValueError, TypeError):
        return False


async def _fetch_with_cache(url: str, validate_404: bool = False) -> dict:
    db = SessionLocal()
    try:
        cached = db.query(JikanCache).filter(JikanCache.request_url == url).first()
        if cached:
            cached_data = json.loads(cached.response_json)
            if validate_404 and cached_data.get("error"):
                return None
            return cached_data

        await asyncio.sleep(RATE_LIMIT_DELAY)

        print(f"[Jikan API] Requesting: {url}")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                stmt = (
                    sqlite_insert(JikanCache)
                    .values(
                        request_url=url,
                        response_json=json.dumps(data, ensure_ascii=False),
                        created_at=datetime.now().isoformat(),
                    )
                    .on_conflict_do_update(
                        index_elements=["request_url"],
                        set_={
                            "response_json": json.dumps(data, ensure_ascii=False),
                            "created_at": datetime.now().isoformat(),
                        },
                    )
                )
                try:
                    db.execute(stmt)
                    db.commit()
                except Exception as e:
                    db.rollback()
                    print(f"[Cache] Erro ao salvar cache para {url}: {e}")
                return data
            elif resp.status_code == 429:
                print("[Jikan API] Rate limit atingido. Aguardando...")
                await asyncio.sleep(5.0)
                return await _fetch_with_cache(url)
            elif resp.status_code == 404 and validate_404:
                print(f"[Jikan API] Anime não encontrado: {url}")
                return None
            else:
                print(f"[Jikan API ERRO] Status: {resp.status_code}")
                return None
    except Exception as e:
        print(f"[Jikan API EXCEÇÃO] {e}")
        return None
    finally:
        db.close()


async def search_anime(query: str):
    url = f"{JIKAN_BASE_URL}/anime?q={query}&limit=20&sfw=true"
    return await _fetch_with_cache(url)


async def get_anime_details(mal_id: int):
    if not _is_valid_mal_id(mal_id):
        print(f"[Jikan] MAL ID inválido: {mal_id}")
        return None
    url = f"{JIKAN_BASE_URL}/anime/{mal_id}/full"
    return await _fetch_with_cache(url, validate_404=True)


async def get_anime_episodes(mal_id: int, page: int = 1):
    if not _is_valid_mal_id(mal_id):
        print(f"[Jikan] MAL ID inválido: {mal_id}")
        return None
    url = f"{JIKAN_BASE_URL}/anime/{mal_id}/episodes?page={page}"
    return await _fetch_with_cache(url, validate_404=True)


async def get_top_animes():
    url = f"{JIKAN_BASE_URL}/top/anime?filter=bypopularity"
    return await _fetch_with_cache(url)


async def get_season_animes():
    url = f"{JIKAN_BASE_URL}/seasons/now"
    return await _fetch_with_cache(url)
