import os
import asyncio
from typing import Optional, Any

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


def _build_episode_stmt(
    media_id: int,
    season_number: int,
    episode_number: int,
    title: str,
    thumbnail_url: str | None,
) -> Any:
    """Builds INSERT statement with ON CONFLICT DO UPDATE."""
    return (
        sqlite_insert(MediaEpisode)
        .values(
            media_id=media_id,
            season_number=season_number,
            episode_number=episode_number,
            title=title,
            thumbnail_url=thumbnail_url,
        )
        .on_conflict_do_update(
            index_elements=["media_id", "season_number", "episode_number"],
            set_={"title": title, "thumbnail_url": thumbnail_url},
        )
    )


def _get_sync_lock(external_id: str, prefix: str = "mal") -> asyncio.Lock:
    key = f"{prefix}_{external_id}"
    if key not in _sync_locks:
        _sync_locks[key] = asyncio.Lock()
    return _sync_locks[key]


async def _detect_season_from_relations(data: dict) -> int:
    """Detecta o número da temporada analisando relations do Jikan."""
    relations = data.get("relations", [])
    tv_prequel_count = 0
    for rel in relations:
        if rel.get("relation") == "prequel":
            entry_type = rel.get("entry", [])
            for entry in entry_type:
                rel_type = entry.get("type", "")
                if rel_type == "anime":
                    tv_prequel_count += 1
    return tv_prequel_count + 1


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

        # Detecta temporada via relations
        season_number = await _detect_season_from_relations(data)
        # Season detection log kept lightweight
        print(f"[Sync] Temporada detectada: {season_number} para MAL {mal_id}")

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

        # Para ANIMES: Usa apenas Jikan (sem TMDB enrichment para evitar conflictos)
        # O TMDB pode retornar dados de spin-offs como Vigilantes
        tmdb_enrichment = {}
        tmdb_meta = {}
        print(f"[Sync] Usando dados 100% Jikan para anime MAL {mal_id}")

        # 2. Salva/Atualiza Mídia (dados 100% do Jikan)
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

        # Busca episódios do Jikan (paginado se necessário) — define a contagem real
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

        # Cruza com episódios disponíveis no animefire para evitar "episódios fantasmas"
        provider_episodes = set()
        try:
            from app.services.scraper import (
                resolve_provider_slug,
                list_provider_episodes,
                search_provider_candidates,
            )

            provider_url = await resolve_provider_slug(
                mal_id, target_title=title, season_hint=season_number
            )
            if provider_url:
                # Usa o slug completo da URL (animefire precisa do slug completo)
                full_slug = provider_url.rstrip("/").split("/")[-1]
                provider_episodes = set(await list_provider_episodes(full_slug))
                print(
                    f"[Sync] Animefire tem {len(provider_episodes)} episódios disponíveis para MAL {mal_id} S{season_number} (via slug cache)"
                )
            else:
                # Fallback: busca direta pelo título no provider
                print(
                    f"[Sync] Slug não encontrado no cache, buscando '{title}' no animefire..."
                )
                candidates = await search_provider_candidates(title)
                if candidates:
                    full_slug = candidates[0].rstrip("/").split("/")[-1]
                    provider_episodes = set(await list_provider_episodes(full_slug))
                    print(
                        f"[Sync] Animefire tem {len(provider_episodes)} episódios disponíveis para MAL {mal_id} (via busca direta)"
                    )
                else:
                    print(
                        f"[Sync] Nenhum candidato encontrado no animefire para '{title}'"
                    )
        except Exception as e:
            print(f"[Sync] Erro ao verificar episódios no provider: {e}")

        is_available_in_provider = bool(provider_url or provider_episodes)
        media.available = is_available_in_provider

        if not is_available_in_provider:
            print(
                f"[Sync] Anime MAL {mal_id} não disponível no provedor. Ignorando episódios e definindo available=False."
            )
        elif not all_episodes:
            new_ep = MediaEpisode(
                media_id=media.id,
                season_number=season_number,
                episode_number=1,
                title="Episódio 01",
                thumbnail_url=media.poster_url,
            )
            db.add(new_ep)
        else:
            for ep in all_episodes:
                real_num = ep.get("number") or ep.get("mal_id")
                if not real_num:
                    continue

                # Se conseguimos a lista do provider, só insere eps disponíveis
                if provider_episodes and real_num not in provider_episodes:
                    print(f"[Sync] Pulando EP {real_num} (não disponível no animefire)")
                    continue

                # Usa dados do TMDB se disponíveis, senão fallback Jikan
                enriched = tmdb_enrichment.get(real_num, {})
                ep_title = (
                    enriched.get("title") or ep.get("title") or f"Episódio {real_num}"
                )
                ep_thumbnail = enriched.get("thumbnail_url") or media.poster_url

                stmt = (
                    sqlite_insert(MediaEpisode)
                    .values(
                        media_id=media.id,
                        season_number=season_number,
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

            # Após processar todos os eps do Jikan, criar placeholders para eps que existem
            # no provider mas não estão no Jikan (ex: One Piece eps 101-474)
            if provider_episodes:
                jikan_nums = {
                    ep.get("number") or ep.get("mal_id")
                    for ep in all_episodes
                    if ep.get("number") or ep.get("mal_id")
                }
                missing_nums = sorted(provider_episodes - jikan_nums)

                if missing_nums:
                    print(
                        f"[Sync] Criando {len(missing_nums)} placeholders (provider-only)"
                    )
                    for num in missing_nums:
                        placeholder_stmt = (
                            sqlite_insert(MediaEpisode)
                            .values(
                                media_id=media.id,
                                season_number=season_number,
                                episode_number=num,
                                title=f"Episódio {num}",
                                thumbnail_url=media.poster_url,
                            )
                            .on_conflict_do_update(
                                index_elements=[
                                    "media_id",
                                    "season_number",
                                    "episode_number",
                                ],
                                set_={
                                    "title": f"Episódio {num}",
                                    "thumbnail_url": media.poster_url,
                                },
                            )
                        )
                        db.execute(placeholder_stmt)

                    print(
                        f"[Sync] Placeholders criados: eps {missing_nums[0]}-{missing_nums[-1]}"
                    )

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
