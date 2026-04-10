import asyncio
import json
from datetime import datetime, timedelta
from time import time
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db, SessionLocal
from app.models import Media, ApiCache
from app.schemas import MediaOut
from app.services.tmdb import search_tmdb
from app.services.jikan import search_anime
from app.limiter import limiter

router = APIRouter(prefix="/api", tags=["catalog"])

# ─── Cache em Memória (Layer 1) ──────────────────────────────────────────────
_AVAILABILITY_CACHE: dict = {}  # {mal_id: (is_available, timestamp)}
_MEM_SEARCH_CACHE: dict = {}  # {q: (results, timestamp)}
_CACHE_TTL = 86400  # 24h — disponibilidade de anime
_SEARCH_MEM_TTL = 600  # 10 min — busca em memória

# ─── TTL de Cache no Banco (Layer 2) ─────────────────────────────────────────
_SEARCH_DB_TTL_DAYS = 7


@router.get("/catalog")
async def get_catalog(
    content_type: Optional[str] = None, db: Session = Depends(get_db)
):
    """Return all media filtered by content_type if provided."""
    query = db.query(Media)
    if content_type:
        query = query.filter(Media.media_type == content_type)
    return query.all()


# Helpers de Disponibilidade


async def _check_anime_available(mal_id: int) -> bool:
    """Verifica se um anime está disponível no animefire, com cache em memória (Layer 1)."""
    now = time()
    if mal_id in _AVAILABILITY_CACHE:
        cached_result, timestamp = _AVAILABILITY_CACHE[mal_id]
        if now - timestamp < _CACHE_TTL:
            return cached_result

    from app.services.scraper import resolve_provider_slug

    try:
        slug = await resolve_provider_slug(mal_id)
        is_available = slug is not None
    except Exception:
        is_available = False

    _AVAILABILITY_CACHE[mal_id] = (is_available, now)
    return is_available


# Helpers de Cache no Banco


def _get_db_cache(q: str) -> list | None:
    """Busca resultado cacheado no banco de dados. Retorna None se expirado/ausente."""
    db = SessionLocal()
    try:
        entry = db.query(ApiCache).filter(ApiCache.query == q.lower().strip()).first()
        if not entry:
            return None
        # Verifica TTL
        if entry.expires_at:
            try:
                expires = datetime.fromisoformat(entry.expires_at)
                if datetime.utcnow() > expires:
                    db.delete(entry)
                    db.commit()
                    return None
            except Exception:
                pass
        return json.loads(entry.result_json) if entry.result_json else None
    except Exception:
        return None
    finally:
        db.close()


def _set_db_cache(q: str, results: list) -> None:
    """Salva resultado de busca no banco, expirando em 7 dias."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        expires = now + timedelta(days=_SEARCH_DB_TTL_DAYS)
        entry = db.query(ApiCache).filter(ApiCache.query == q.lower().strip()).first()
        if entry:
            entry.result_json = json.dumps(results)
            entry.verified_at = now.isoformat()
            entry.expires_at = expires.isoformat()
        else:
            entry = ApiCache(
                query=q.lower().strip(),
                result_json=json.dumps(results),
                verified_at=now.isoformat(),
                expires_at=expires.isoformat(),
            )
            db.add(entry)
        db.commit()
    except Exception as e:
        print(f"[Search Cache DB] Erro ao salvar: {e}")
    finally:
        db.close()


# Rota de Busca
@router.get("/search")
@limiter.limit("20/minute")
async def search_media(request: Request, q: str, media_type: Optional[str] = None):
    """
    Busca bifurcada com cache 3 camadas:
      1. Memória (10 min)
      2. Banco de dados (7 dias)
      3. API (Jikan/TMDB) + scraper para verificar disponibilidade.
    """
    if not q or len(q.strip()) < 2:
        return []

    cache_key = q.lower().strip()

    # Layer 1: Cache em memória
    if cache_key in _MEM_SEARCH_CACHE:
        cached_results, ts = _MEM_SEARCH_CACHE[cache_key]
        if time() - ts < _SEARCH_MEM_TTL:
            return cached_results

    # Layer 2: Cache no banco
    db_cached = _get_db_cache(cache_key)
    if db_cached is not None:
        _MEM_SEARCH_CACHE[cache_key] = (db_cached, time())  # promove para memória
        return db_cached

    # Layer 3: APIs externas
    results = []

    jikan_task = None
    tmdb_task = None

    if media_type is None or media_type == "anime":
        jikan_task = asyncio.create_task(search_anime(q))
    if media_type is None or media_type in ["western", "desenho"]:
        tmdb_task = asyncio.create_task(search_tmdb(q))

    # 1. Jikan (Animes)
    if jikan_task:
        try:
            jikan_data = await jikan_task
            if jikan_data and "data" in jikan_data:
                items_to_check = jikan_data["data"][:10]

                unique_items = []
                seen_ids: set = set()
                for it in items_to_check:
                    m_id = it.get("mal_id")
                    if m_id and m_id not in seen_ids:
                        seen_ids.add(m_id)
                        unique_items.append(it)

                # 直接格式化成结果，不检查可用性
                for item in unique_items:
                    mal_id = item.get("mal_id")
                    results.append(
                        {
                            "id": f"mal_{mal_id}",
                            "mal_id": mal_id,
                            "title": item.get("title"),
                            "synopsis": item.get("synopsis"),
                            "poster_url": item.get("images", {})
                            .get("jpg", {})
                            .get("image_url"),
                            "media_type": "anime",
                            "year": str(item.get("year") or ""),
                        }
                    )
        except Exception as e:
            print(f"[Search] Erro Jikan: {e}")

    # 2. TMDB (Filmes/Séries/Desenhos)
    if tmdb_task:
        try:
            tmdb_results = await tmdb_task
            for r in tmdb_results:
                r["id"] = f"tmdb_{r.get('id')}"
            results.extend(tmdb_results)
        except Exception as e:
            print(f"[Search] Erro TMDB: {e}")

    # Motor de relevância
    query_lower = q.lower().strip()

    def _relevance(item: dict) -> int:
        title = item.get("title", item.get("name", "")).lower()
        title_eng = item.get("title_english", "").lower()
        if query_lower in (title, title_eng):
            return 0
        if title.startswith(query_lower) or title_eng.startswith(query_lower):
            return 1
        if query_lower in title or query_lower in title_eng:
            return 2
        return 3

    results.sort(key=_relevance)

    # Persiste no cache (Layer 1 + 2), só se tiver resultados
    if results:
        _MEM_SEARCH_CACHE[cache_key] = (results, time())
        asyncio.create_task(asyncio.to_thread(_set_db_cache, cache_key, results))

    return results
