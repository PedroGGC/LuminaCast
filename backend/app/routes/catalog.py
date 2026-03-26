from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Media
from app.schemas import MediaOut
from app.services.tmdb import search_tmdb
from app.services.jikan import search_anime

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/catalog")
async def get_catalog(
    content_type: Optional[str] = None, db: Session = Depends(get_db)
):
    """Return all media filtered by content_type if provided."""
    query = db.query(Media)
    if content_type:
        query = query.filter(Media.media_type == content_type)
    return query.all()


@router.get("/search")
async def search_media(q: str, media_type: Optional[str] = None):
    """
    Busca bifurcada:
    - media_type == 'anime'   → apenas Jikan.
    - media_type == 'western' → apenas TMDB.
    - None                    → ambos, unificados.
    """
    if not q or len(q.strip()) < 2:
        return []

    results = []

    # 1. Jikan (Animes)
    if media_type is None or media_type == "anime":
        try:
            jikan_data = await search_anime(q)
            if jikan_data and "data" in jikan_data:
                for item in jikan_data["data"]:
                    results.append(
                        {
                            "id": f"mal_{item.get('mal_id')}",
                            "mal_id": item.get("mal_id"),
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

    # 2. TMDB (Filmes/Séries/Desenhos) — filtro aplicado em search_tmdb
    if media_type is None or media_type in ["western", "desenho"]:
        try:
            tmdb_results = await search_tmdb(q)
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
    return results
