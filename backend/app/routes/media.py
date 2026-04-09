import asyncio
import io
import os
import zipfile
import httpx
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter

# Importa o modelo de mapping anime->MAL ID aqui
from app.models import Media, MediaEpisode, AnimeMapping
from app.schemas import MediaOut, MediaEpisodeOut
from app.services.scraper import extract_episode_url

# Importa o serviço de sincronização (refatorado)
from app.services.sync_service import sync_media_by_id

router = APIRouter(prefix="/api", tags=["media"])

DUMMY_VIDEO_URL = (
    "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
)


def _resolve_media_prefix(media_id: str) -> tuple[str, str | None]:
    """Resolve prefix from media_id and return (clean_id, media_type)."""
    media_type = None
    if media_id.startswith("mal_"):
        media_type = "anime"
        media_id = media_id.replace("mal_", "")
    elif media_id.startswith("tmdb_"):
        media_type = "desenho"
        media_id = media_id.replace("tmdb_", "")
    return media_id, media_type


def _get_media_by_query(
    db: Session, media_id: str, media_type: str | None
) -> Media | None:
    """Generic media query by external_id or internal id."""
    if media_type in ("anime", "desenho"):
        return db.query(Media).filter(Media.external_id == media_id).first()
    elif media_id.isdigit():
        return (
            db.query(Media)
            .filter((Media.id == int(media_id)) | (Media.external_id == media_id))
            .first()
        )
    return db.query(Media).filter(Media.external_id == media_id).first()


# ─── Listações de Mídia ────────────────────────────────────────────────────────────────


@router.get("/media/animes", response_model=list[MediaOut])
async def get_animes(db: Session = Depends(get_db)):
    from sqlalchemy import func

    return (
        db.query(Media)
        .join(MediaEpisode, Media.id == MediaEpisode.media_id, isouter=True)
        .filter(Media.media_type == "anime")
        .group_by(Media.id)
        .having(func.count(MediaEpisode.id) > 0)
        .all()
    )


@router.get("/media/desenhos", response_model=list[MediaOut])
async def get_desenhos(db: Session = Depends(get_db)):
    from sqlalchemy import func

    return (
        db.query(Media)
        .join(MediaEpisode, Media.id == MediaEpisode.media_id, isouter=True)
        .filter(Media.media_type == "desenho")
        .group_by(Media.id)
        .having(func.count(MediaEpisode.id) > 0)
        .all()
    )


@router.get("/media/{media_id}")
async def get_media_detail(
    media_id: str, media_type: Optional[str] = None, db: Session = Depends(get_db)
):
    if media_id == "undefined":
        raise HTTPException(status_code=400, detail="Invalid Media ID")

    media_id, media_type = _resolve_media_prefix(media_id)
    media = _get_media_by_query(db, media_id, media_type)

    # ─── 3. Fallback de Segurança (para Itens do Seed) ───
    # Se ainda não sabe o tipo, a mídia não está no banco e o ID é numérico
    if not media and not media_type and media_id.isdigit():
        from app.models import AnimeMapping  # Importa o modelo de mapping anime->MAL ID

        is_seeded_anime = (
            db.query(AnimeMapping).filter(AnimeMapping.mal_id == int(media_id)).first()
        )
        if is_seeded_anime:
            media_type = "anime"

    # ─── 4. JIT Sync (Sincronização em Tempo Real) ───
    # P1.1: Sincroniza em background se não houver episódios
    has_episodes = False
    if media:
        has_episodes = (
            db.query(MediaEpisode).filter(MediaEpisode.media_id == media.id).count() > 0
        )
        if not media_type:
            media_type = (
                media.media_type
            )  # Pega o tipo do banco para garantir a sincronização correta

    if not media or not has_episodes:
        print(
            f"[JIT Sync] Gatilho acionado para mídia {media_id} (Tipo: {media_type}). Agendando em background..."
        )
        background_tasks.add_task(_run_background_sync, str(media_id), media_type)
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=202,
            content={
                "message": "Sincronização em andamento. Por favor, tente novamente em alguns segundos.",
                "status": "syncing",
            },
        )

    # Retorna o item que já estava no banco (não necesitamos mais forçar expirações na thread principal)
    return media


async def _run_background_sync(media_id: str, media_type: Optional[str]):
    """Helper para rodar o JIT Sync no background com nova sessão do DB."""
    from app.database import SessionLocal
    from app.services.sync_service import sync_media_by_id

    db = SessionLocal()
    try:
        await sync_media_by_id(media_id, media_type, db)
    except Exception as e:
        print(f"[Background Sync Error] {e}")
    finally:
        db.close()


@router.get("/media/{media_id}/check-source")
async def check_media_source(
    media_id: str,
    episode_number: int = Query(default=1),
    season_number: int = Query(default=1),
    db: Session = Depends(get_db),
):
    """Rota leve para verificar a fonte do vídeo sem fazer scraping completo."""
    if media_id == "undefined":
        raise HTTPException(status_code=400, detail="Invalid Media ID")

    if media_id.startswith("mal_"):
        media_type = "anime"
        media_id = media_id.replace("mal_", "")
    elif media_id.startswith("tmdb_"):
        media_type = "desenho"
        media_id = media_id.replace("tmdb_", "")

    # Se veio com prefixo mal_ ou tmdb_, sempre busca por external_id
    media = None
    if media_type in ("anime", "desenho"):
        media = db.query(Media).filter(Media.external_id == media_id).first()
    elif media_id.isdigit():
        media = (
            db.query(Media)
            .filter((Media.id == int(media_id)) | (Media.external_id == media_id))
            .first()
        )
    else:
        media = db.query(Media).filter(Media.external_id == media_id).first()

    if not media:
        return {"source": "unknown", "can_download": True}

    target_episode = (
        db.query(MediaEpisode)
        .filter(
            MediaEpisode.media_id == media.id,
            MediaEpisode.season_number == season_number,
            MediaEpisode.episode_number == episode_number,
        )
        .first()
    )

    if not target_episode:
        target_episode = (
            db.query(MediaEpisode)
            .filter(MediaEpisode.media_id == media.id)
            .order_by(
                MediaEpisode.season_number.asc(), MediaEpisode.episode_number.asc()
            )
            .first()
        )

    if not target_episode:
        return {"source": "unknown", "can_download": True}

    try:
        from app.services.scraper import extract_episode_url

        raw_url = await extract_episode_url(
            external_id=str(media.external_id),
            title=media.title,
            original_title=media.original_title or media.title,
            season=target_episode.season_number,
            episode=target_episode.episode_number,
            media_type=media.media_type,
        )

        if raw_url and ("blogger.com" in raw_url or "video.g" in raw_url):
            return {"source": "blogger", "can_download": False}

        return {"source": "direct", "can_download": True}
    except Exception as e:
        print(f"[CheckSource] Erro: {e}")
        return {"source": "error", "can_download": True}


@router.get("/media/{media_id}/full")
async def get_media_full(
    background_tasks: BackgroundTasks,
    media_id: str,
    media_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Endpoint otimizado que carrega todos os dados de uma vez.
    Retorna 202 Accepted se o JIT Sync estiver em andamento.
    Retorna 200 OK: { media, episodes, can_download }
    """
    if media_id == "undefined":
        raise HTTPException(status_code=400, detail="Invalid Media ID")

    # Resolvedor de prefixo
    if media_id.startswith("mal_"):
        media_type = "anime"
        media_id = media_id.replace("mal_", "")
    elif media_id.startswith("tmdb_"):
        media_type = "desenho"
        media_id = media_id.replace("tmdb_", "")

    # Se veio com prefixo mal_ ou tmdb_, sempre busca por external_id
    media = None
    if media_type in ("anime", "desenho"):
        media = db.query(Media).filter(Media.external_id == media_id).first()
    elif media_id.isdigit():
        media = (
            db.query(Media)
            .filter((Media.id == int(media_id)) | (Media.external_id == media_id))
            .first()
        )
    else:
        media = db.query(Media).filter(Media.external_id == media_id).first()

    # Fallback de tipo para seed
    if not media and not media_type and media_id.isdigit():
        from app.models import AnimeMapping

        is_seeded_anime = (
            db.query(AnimeMapping).filter(AnimeMapping.mal_id == int(media_id)).first()
        )
        if is_seeded_anime:
            media_type = "anime"

    # Determina se precisa de sync (não existe OU não tem episódios)
    needs_sync = False
    if media:
        has_episodes = (
            db.query(MediaEpisode).filter(MediaEpisode.media_id == media.id).count() > 0
        )
        needs_sync = not has_episodes
        if not media_type:
            media_type = media.media_type
    else:
        needs_sync = True

    # P1.1: Retorna 202 APENAS se é mídia nova (não existe no banco)
    # Se já existe mas sem episódios, retorna dados mesmo assim
    if needs_sync and not media:
        print(
            f"[Full Load] Gatilho acionado para {media_id} (tipo: {media_type}). Agendando sync em background..."
        )
        background_tasks.add_task(_run_background_sync, str(media_id), media_type)
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=202,
            content={
                "status": "syncing",
                "message": "Buscando dados nas APIs externas...",
            },
        )

    db.commit()
    db.expire_all()

    # Recarrega dados frescos
    media = db.query(Media).filter(Media.id == media.id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Mídia não encontrada")
    episodes = db.query(MediaEpisode).filter(MediaEpisode.media_id == media.id).all()
    episodes_sorted = sorted(
        episodes, key=lambda x: (x.season_number, x.episode_number)
    )

    # Check source em background (não bloqueia)
    can_download = True
    if episodes_sorted:
        first_ep = episodes_sorted[0]
        try:
            from app.services.scraper import extract_episode_url

            raw_url = await extract_episode_url(
                external_id=str(media.external_id),
                title=media.title,
                original_title=media.original_title or media.title,
                season=first_ep.season_number,
                episode=first_ep.episode_number,
                media_type=media.media_type,
            )
            if raw_url and ("blogger.com" in raw_url or "video.g" in raw_url):
                can_download = False
        except Exception:
            pass

    return {
        "media": {
            "id": media.id,
            "external_id": media.external_id,
            "title": media.title,
            "synopsis": media.synopsis,
            "poster_url": media.poster_url,
            "banner_image": media.backdrop_url,
            "cover_image": media.poster_url,
            "media_type": media.media_type,
            "rating": None,
            "year": None,
        },
        "episodes": episodes_sorted,
        "can_download": can_download,
    }


@router.get("/media/{media_id}/episodes", response_model=list[MediaEpisodeOut])
async def get_media_episodes(
    media_id: str, media_type: Optional[str] = None, db: Session = Depends(get_db)
):
    if media_id == "undefined":
        raise HTTPException(status_code=400, detail="Invalid Media ID")

    # ─── 1. RESOLUÇÃO INTELIGENTE DE PREFIXO E TIPO ───
    if media_id.startswith("mal_"):
        media_type = "anime"
        media_id = media_id.replace("mal_", "")
    elif media_id.startswith("tmdb_"):
        media_type = "desenho"
        media_id = media_id.replace("tmdb_", "")

    # Se veio com prefixo mal_ ou tmdb_, sempre busca por external_id
    media = None
    if media_type in ("anime", "desenho"):
        media = db.query(Media).filter(Media.external_id == media_id).first()
    elif media_id.isdigit():
        media = (
            db.query(Media)
            .filter((Media.id == int(media_id)) | (Media.external_id == media_id))
            .first()
        )
    else:
        media = db.query(Media).filter(Media.external_id == media_id).first()

    if not media and not media_type and media_id.isdigit():
        from app.models import AnimeMapping

        is_seeded_anime = (
            db.query(AnimeMapping).filter(AnimeMapping.mal_id == int(media_id)).first()
        )
        if is_seeded_anime:
            media_type = "anime"

    if not media:
        media = await sync_media_by_id(media_id, media_type, db)
        if not media:
            return []

    # Quebra o Isolamento da Transação: força nova transação para enxergar dados da sincronização
    db.commit()
    db.expire_all()

    episodes = db.query(MediaEpisode).filter(MediaEpisode.media_id == media.id).all()

    if not episodes:
        print(f"[JIT Sync] Episódios vazios para {media_id}. Sincronizando...")
        await sync_media_by_id(media.external_id, media.media_type, db)
        db.commit()
        db.expire_all()
        episodes = (
            db.query(MediaEpisode).filter(MediaEpisode.media_id == media.id).all()
        )

    return sorted(episodes, key=lambda x: (x.season_number, x.episode_number))


# ─── Player / Stream ─────────────────────────────────────────────────────────


@router.get("/stream/{episode_id}")
async def stream_episode(episode_id: int, db: Session = Depends(get_db)):
    episode = db.query(MediaEpisode).filter(MediaEpisode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episódio não encontrado")

    media = db.query(Media).filter(Media.id == episode.media_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Mídia não encontrada")

    external_id = media.external_id
    # Prefixa o external_id para o frontend navegar corretamente
    if media.media_type == "anime":
        prefixed_id = f"mal_{external_id}"
    else:
        prefixed_id = f"tmdb_{external_id}"

    # 2. Busca do Próximo Episódio (Mesma Temporada)
    next_ep_info = None
    next_ep = (
        db.query(MediaEpisode)
        .filter(
            MediaEpisode.media_id == episode.media_id,
            MediaEpisode.season_number == episode.season_number,
            MediaEpisode.episode_number == episode.episode_number + 1,
        )
        .first()
    )

    if next_ep:
        next_ep_info = {
            "id": next_ep.id,
            "number": next_ep.episode_number,
            "title": next_ep.title,
        }

    # 3. Roteamento de Lógica: Anime vs Western
    try:
        if media.media_type == "anime":
            stream_url = await extract_episode_url(
                external_id=external_id,
                title=media.title,
                original_title=media.original_title,
                season=episode.season_number,
                episode=episode.episode_number,
                media_type=media.media_type,
            )
            if not stream_url:
                raise HTTPException(
                    status_code=404,
                    detail="Mídia não encontrada no provedor atual.",
                )
            return {
                "stream_url": stream_url,
                "embed_urls": [],
                "media_id": prefixed_id,
                "title": media.title,
                "season_number": episode.season_number,
                "episode_number": episode.episode_number,
                "media_type": media.media_type,
                "next_episode": next_ep_info,
            }
        else:
            from app.services.embed_providers import get_embed_urls

            embed_urls = get_embed_urls(
                media_type=media.media_type,
                tmdb_id=external_id,
                season=episode.season_number,
                episode=episode.episode_number,
            )
            if not embed_urls:
                raise HTTPException(
                    status_code=404,
                    detail="Mídia não encontrada no provedor atual.",
                )
            return {
                "stream_url": "",
                "embed_urls": embed_urls,
                "media_id": prefixed_id,
                "title": media.title,
                "season_number": episode.season_number,
                "episode_number": episode.episode_number,
                "media_type": media.media_type,
                "next_episode": next_ep_info,
            }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Stream] Erro no roteamento/scraping: {str(e)}")
        return {
            "stream_url": "",
            "embed_urls": [],
            "media_id": prefixed_id,
            "media_type": media.media_type,
            "next_episode": next_ep_info,
        }


@router.get("/download/episode/{episode_id}")
@limiter.limit("15/minute")
async def download_single_episode(
    request: Request, episode_id: int, db: Session = Depends(get_db)
):
    """Proxy download de um episódio real extraído pelo scraper."""

    episode = db.query(MediaEpisode).filter(MediaEpisode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episódio não encontrado")

    # ─── Verificação de Mídia e Extração de URL ────────────────────────────────
    media_type = episode.media.media_type if episode.media else "anime"
    media_title = episode.media.title if episode.media else "Unknown"
    external_id = episode.media.external_id if episode.media else None

    if media_type != "anime" and external_id:
        from app.services.embed_providers import get_embed_urls

        urls = get_embed_urls(
            media_type=media_type,
            tmdb_id=external_id,
            season=episode.season_number,
            episode=episode.episode_number,
        )
        video_url = urls[0] if urls else ""
    else:
        from app.services.scraper import extract_episode_url

        original_title = episode.media.original_title if episode.media else media_title

        video_url = await extract_episode_url(
            external_id=str(external_id),
            title=media_title,
            original_title=original_title,
            season=episode.season_number,
            episode=episode.episode_number,
            media_type=media_type,
        )

    # Blindagem contra falha total
    if not video_url:
        raise HTTPException(status_code=404, detail="URL de vídeo não encontrada.")

    # Task P0.2 - Proteção SSRF
    import urllib.parse
    import ipaddress

    try:
        parsed = urllib.parse.urlparse(video_url)
        if parsed.scheme not in ("http", "https"):
            raise Exception("Scheme não permitido.")
        host = parsed.hostname
        if not host:
            raise Exception("Sem hostname.")
        if host.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            raise Exception("Hostname bloqueado.")

        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise Exception("IP privado/local bloqueado.")
        except ValueError:
            pass  # É um domínio não um IP direto
    except Exception as e:
        print(f"[SSRF Blocked] URL: {video_url} | Motivo: {e}")
        raise HTTPException(
            status_code=400,
            detail="Endpoint de download inválido ou bloqueado por segurança.",
        )

    # Blindagem contra Iframe (Blogger bloqueado)
    if "blogger.com" in video_url or "video.g" in video_url:
        raise HTTPException(
            status_code=403,
            detail="Download não disponível. O provedor bloqueou a extração direta do arquivo.",
        )

    embed_indicators = ["warezcdn.net", "vidsrc.me", "superflixapi.rest"]
    if any(indicator in video_url for indicator in embed_indicators):
        raise HTTPException(
            status_code=400,
            detail="Este episódio utiliza um player externo que não suporta download direto.",
        )

    clean_title = "".join(
        c for c in (episode.title or "Sem_Titulo") if c.isalnum() or c in (" ", "_")
    ).replace(" ", "_")
    filename = (
        f"S{episode.season_number:02d}E{episode.episode_number:02d}_{clean_title}.mp4"
    )

    async def stream_video_proxy():
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=300.0,
            limits=httpx.Limits(max_connections=10),
        ) as client:
            try:
                async with client.stream("GET", video_url) as response:
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 1024 * 4):
                        yield chunk
            except Exception as e:
                print(f"[Download Proxy Error] {e}")

    return StreamingResponse(
        stream_video_proxy(),
        media_type="video/mp4",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


# ─── Download em Lote ─────────────────────────────────────────────────────────


@router.get("/download-batch")
@limiter.limit("5/minute")
async def download_batch(
    request: Request, episode_ids: str = Query(...), db: Session = Depends(get_db)
):
    """
    Recebe IDs separados por vírgula.
    P1.2: Extrai as URLs reais e faz download em disco com arquivos temporários (não usa RAM).
    P1.3: Limita concorrência com Semáforo.
    """

    from sqlalchemy.orm import joinedload
    import tempfile
    import shutil
    import os
    import time
    from starlette.background import BackgroundTask
    from fastapi.responses import FileResponse

    ep_ids = [int(i.strip()) for i in episode_ids.split(",") if i.strip().isdigit()]
    if not ep_ids:
        raise HTTPException(status_code=400, detail="Nenhum episódio válido fornecido")

    eps = (
        db.query(MediaEpisode)
        .options(joinedload(MediaEpisode.media))
        .filter(MediaEpisode.id.in_(ep_ids))
        .order_by(MediaEpisode.season_number, MediaEpisode.episode_number)
        .all()
    )
    if not eps:
        raise HTTPException(status_code=404, detail="Episódios não encontrados")

    ep_data = []
    for ep in eps:
        ep_data.append(
            {
                "id": ep.id,
                "episode_number": ep.episode_number,
                "season_number": ep.season_number,
                "title": ep.title,
                "media_type": ep.media.media_type if ep.media else "anime",
                "media_title": ep.media.title if ep.media else "Unknown",
                "external_id": ep.media.external_id if ep.media else None,
            }
        )

    from app.services.scraper import (
        extract_episode_url,
        resolve_provider_slug,
        get_cached_slug as scraper_get_cached_slug,
    )

    async def get_cached_slug(media_type, external_id, title, season_hint=None):
        if media_type != "anime" or not external_id:
            return None
        mal_id = int(external_id) if external_id.isdigit() else None
        if not mal_id:
            return None

        cached = scraper_get_cached_slug(mal_id)
        if cached:
            return cached

        url = await resolve_provider_slug(mal_id, season_hint=season_hint)
        if url:
            return url.split("/")[-1] if "/" in url else url
        return None

    embed_indicators_block = [
        "blogger.com",
        "warezcdn.net",
        "vidsrc.me",
        "superflixapi.top",
        "video.g",
    ]

    tmp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(
        tempfile.gettempdir(), f"batch_download_{int(time.time())}.zip"
    )

    # Limite de 5 downloads simultâneos
    sem = asyncio.Semaphore(5)

    async def download_single_ep(ep, client):
        """Baixa arquivo temp no disco e retorna (filename, filepath)."""
        async with sem:
            media_type = ep["media_type"]
            media_title = ep["media_title"]
            external_id = ep["external_id"]

            try:
                if media_type != "anime" and external_id:
                    from app.services.embed_providers import get_embed_urls

                    urls = get_embed_urls(
                        media_type=media_type,
                        tmdb_id=external_id,
                        season=ep["season_number"],
                        episode=ep["episode_number"],
                    )
                    video_url = urls[0] if urls else ""
                else:
                    original_title = media_title
                    cached_slug = await get_cached_slug(
                        media_type, external_id, media_title
                    )
                    video_url = await extract_episode_url(
                        external_id=str(external_id),
                        title=media_title,
                        original_title=original_title,
                        season=ep["season_number"],
                        episode=ep["episode_number"],
                        media_type=media_type,
                        cached_slug=cached_slug,
                    )

                if (
                    any(ind in video_url for ind in embed_indicators_block)
                    or "http" not in video_url
                ):
                    print(
                        f"[Batch ZIP] Pulando EP {ep['episode_number']} (Externo/Invalido)"
                    )
                    return None

                clean_title = "".join(
                    c
                    for c in (ep["title"] or "Sem_Titulo")
                    if c.isalnum() or c in (" ", "_")
                ).replace(" ", "_")
                fname = f"S{ep['season_number']:02d}E{ep['episode_number']:02d}_{clean_title}.mp4"
                file_path = os.path.join(tmp_dir, fname)

                async with client.stream("GET", video_url) as response:
                    if response.status_code == 200:
                        with open(file_path, "wb") as f:
                            async for chunk in response.aiter_bytes(
                                chunk_size=1024 * 1024 * 4
                            ):
                                f.write(chunk)
                        print(f"[Batch ZIP] Arquivo salvo EP {ep['episode_number']}")
                        return (file_path, fname)
            except Exception as e:
                print(f"[Batch ZIP Error] Erro no episódio {ep['id']}: {e}")
            return None

    # Dispara os downloads pro disco
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=1200.0,  # Tempo estendido para batch longo
        limits=httpx.Limits(max_connections=20),
    ) as client:
        tasks = [download_single_ep(ep, client) for ep in ep_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Cria o arquivo ZIP sincronamente lendo o disco
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
        for result in results:
            if isinstance(result, tuple) and result:
                filepath, arcname = result
                zf.write(filepath, arcname)
                print(f"[Batch ZIP] Adicionado ao ZIP: {arcname}")
            elif isinstance(result, Exception):
                print(f"[Batch ZIP Error] Task exception: {result}")

    def cleanup_func():
        """Remove o temporário e o ZIP final."""
        shutil.rmtree(tmp_dir, ignore_errors=True)
        try:
            if os.path.exists(zip_path):
                os.remove(zip_path)
        except OSError:
            pass

    cleanup_task = BackgroundTask(cleanup_func)

    return FileResponse(
        path=zip_path,
        filename="episodios.zip",
        media_type="application/x-zip-compressed",
        background=cleanup_task,
        headers={
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
