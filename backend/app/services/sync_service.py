import os
import asyncio
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy import func

from app.models import Media, MediaEpisode
from app.core.http_client import get_http_client
from app.services.tmdb import (
    get_tmdb_details,
    get_tmdb_episodes,
    TMDB_IMG_W500,
    TMDB_IMG_ORIGINAL,
)
from app.services.jikan import get_anime_details, get_anime_episodes

TMDB_BASE = "https://api.themoviedb.org/3"

_sync_locks: dict[str, asyncio.Lock] = {}
_sync_done: set[str] = set()


def _get_sync_lock(external_id: str, prefix: str = "mal") -> asyncio.Lock:
    key = f"{prefix}_{external_id}"
    if key not in _sync_locks:
        _sync_locks[key] = asyncio.Lock()
    return _sync_locks[key]


async def sync_anime_by_mal_id(mal_id: int, db: Session):
    """
    Sincroniza metadados e episódios de Anime via MyAnimeList (Jikan).
    Com lock de concorrência para evitar episódios duplicados.
    """
    key = f"mal_{mal_id}"
    lock = _get_sync_lock(str(mal_id), "mal")

    async with lock:
        print(f"[Jit Sync] Gatilho acionado para mídia {mal_id}. Sincronizando...")

        existing_eps = (
            db.query(func.count())
            .select_from(MediaEpisode)
            .join(Media, Media.id == MediaEpisode.media_id)
            .filter(Media.external_id == str(mal_id))
            .scalar()
        )

        # Apenas pula sync se JÁ tem episódios (não usa mais _sync_done cache)
        if existing_eps and existing_eps > 0:
            _sync_done.add(key)
            print(f"[Jit Sync] Episódios já existem no banco para {key}, pulando sync.")
            return None

        print(f"[Jit Sync] Sincronizando Anime MAL ID: {mal_id}")

        # 1. Busca detalhes do Jikan
        details_wrap = await get_anime_details(mal_id)
        if not details_wrap or "data" not in details_wrap:
            return None

        data = details_wrap["data"]
        title = data.get("title")
        original = data.get("title_japanese") or title
        synopsis = data.get("synopsis")
        poster = data.get("images", {}).get("webp", {}).get("large_image_url")
        backdrop = data.get("images", {}).get("webp", {}).get("image_url")

        # Extrai o ano de lançamento para validação posterior
        jikan_year = None
        aired = data.get("aired", {})
        if aired:
            aired_from = aired.get("from", "")
            if aired_from:
                try:
                    jikan_year = int(aired_from.split("-")[0])
                except (ValueError, IndexError):
                    pass
        if not jikan_year:
            jikan_year = data.get("year")

        # 2. Animes usam 100% dados nativos do Jikan (TMDB proibido para animes)
        print(f"[Enrichment] Mídia tipo 'anime'. Usando dados nativos do Jikan.")

        # 3. Salva/Atualiza Mídia
        media = (
            db.query(Media)
            .filter((Media.external_id == str(mal_id)) & (Media.media_type == "anime"))
            .first()
        )

        if not media:
            media = Media(
                external_id=str(mal_id),
                title=title,
                original_title=original,
                synopsis=synopsis,
                poster_url=poster,
                backdrop_url=backdrop,
                media_type="anime",
            )
            db.add(media)
        else:
            media.title = title
            media.synopsis = synopsis
            media.poster_url = poster
            media.backdrop_url = backdrop

        db.commit()
        db.refresh(media)

        # 4. Sincroniza Episódios (Limpa Antigos Primeiro)
        db.query(MediaEpisode).filter_by(media_id=media.id).delete()
        db.commit()

        # Busca episódios (paginado se necessário)
        all_episodes = []
        page = 1
        while True:
            ep_resp = await get_anime_episodes(mal_id, page)
            if not ep_resp or "data" not in ep_resp:
                break

            all_episodes.extend(ep_resp["data"])

            pagination = ep_resp.get("pagination", {})
            if not pagination.get("has_next_page"):
                break
            page += 1
            if page > 5:
                break

        if not all_episodes:
            new_ep = MediaEpisode(
                media_id=media.id,
                season_number=1,
                episode_number=1,
                title="Episódio 01",
                thumbnail_url=media.poster_url,
            )
            db.add(new_ep)
        else:
            for ep in all_episodes:
                real_num = ep.get("number") or ep.get("mal_id")
                ep_title = ep.get("title") or f"Episódio {real_num}"
                ep_thumbnail = media.poster_url

                stmt = (
                    sqlite_insert(MediaEpisode)
                    .values(
                        media_id=media.id,
                        season_number=1,
                        episode_number=real_num,
                        title=ep_title,
                        thumbnail_url=ep_thumbnail,
                    )
                    .on_conflict_do_update(
                        index_elements=["media_id", "season_number", "episode_number"],
                        set_={
                            "title": ep_title,
                            "thumbnail_url": ep_thumbnail,
                        },
                    )
                )
                db.execute(stmt)

        db.commit()
        _sync_done.add(key)
        print(f"[Jit Sync] Sync concluído para {key}")
        return media


async def sync_media_by_id(external_id: str, media_type: Optional[str], db: Session):
    """
    Roteador Central de Sincronização.
    """
    if not external_id or external_id == "undefined":
        return None

    # Auto-resolução de prefixos caso não tenham sido removidos antes
    if str(external_id).startswith("mal_"):
        media_type = "anime"
        external_id = external_id.replace("mal_", "")
    elif str(external_id).startswith("tmdb_"):
        media_type = "desenho"
        external_id = external_id.replace("tmdb_", "")

    if media_type == "anime":
        try:
            return await sync_anime_by_mal_id(int(external_id), db)
        except (ValueError, TypeError):
            print(f"[Sync] ID de anime inválido: {external_id}")
            return None

    tmdb_key = os.getenv("TMDB_API_KEY", "").strip()
    if not tmdb_key:
        return None

    lock = _get_sync_lock(str(external_id), "tmdb")

    async with lock:
        try:
            tmdb_data = await get_tmdb_details(int(external_id))
            if not tmdb_data or "id" not in tmdb_data:
                return None

            actual_type = tmdb_data.get("media_type_actual", "tv")
            poster_path = tmdb_data.get("poster_path")
            title = tmdb_data.get("name") or tmdb_data.get("title")
            original = (
                tmdb_data.get("original_name")
                or tmdb_data.get("original_title")
                or title
            )

            media = (
                db.query(Media).filter(Media.external_id == str(external_id)).first()
            )
            if not media:
                media = Media(
                    external_id=str(external_id),
                    title=title,
                    original_title=original,
                    synopsis=tmdb_data.get("overview"),
                    poster_url=f"{TMDB_IMG_ORIGINAL}{poster_path}"
                    if poster_path
                    else None,
                    media_type=media_type
                    if media_type
                    else ("anime" if actual_type == "tv" else "filme"),
                )
                db.add(media)
            else:
                media.synopsis = tmdb_data.get("overview")
                if poster_path:
                    media.poster_url = f"{TMDB_IMG_ORIGINAL}{poster_path}"

            db.commit()
            db.refresh(media)

            client = get_http_client()
            if actual_type == "tv":
                seasons_list = tmdb_data.get("seasons", [])
                for season in seasons_list:
                    s_num = season.get("season_number", 0)
                    if s_num == 0:
                        continue

                    ep_resp = await client.get(
                        f"{TMDB_BASE}/tv/{external_id}/season/{s_num}",
                        params={"api_key": tmdb_key, "language": "pt-BR"},
                    )

                    if ep_resp.status_code == 200:
                        for ep in ep_resp.json().get("episodes", []):
                            still_path = ep.get("still_path")
                            ep_num = ep.get("episode_number", 0)
                            stmt = (
                                sqlite_insert(MediaEpisode)
                                .values(
                                    media_id=media.id,
                                    season_number=s_num,
                                    episode_number=ep_num,
                                    title=ep.get("name"),
                                    thumbnail_url=f"https://image.tmdb.org/t/p/w500{still_path}"
                                    if still_path
                                    else media.poster_url,
                                )
                                .on_conflict_do_update(
                                    index_elements=[
                                        "media_id",
                                        "season_number",
                                        "episode_number",
                                    ],
                                    set_={
                                        "title": ep.get("name"),
                                        "thumbnail_url": f"https://image.tmdb.org/t/p/w500{still_path}"
                                        if still_path
                                        else media.poster_url,
                                    },
                                )
                            )
                            db.execute(stmt)
                        db.commit()
            else:
                # Filme
                stmt = (
                    sqlite_insert(MediaEpisode)
                    .values(
                        media_id=media.id,
                        season_number=0,
                        episode_number=1,
                        title="Filme Completo",
                        thumbnail_url=media.poster_url,
                    )
                    .on_conflict_do_update(
                        index_elements=[
                            "media_id",
                            "season_number",
                            "episode_number",
                        ],
                        set_={
                            "title": "Filme Completo",
                            "thumbnail_url": media.poster_url,
                        },
                    )
                )
                db.execute(stmt)
                db.commit()

            db.expire_all()
            return media

        except Exception as e:
            print(f"[JIT Sync] ERRO: {e}")
            db.rollback()
            raise e
