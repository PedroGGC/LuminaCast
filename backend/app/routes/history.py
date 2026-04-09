import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import WatchHistory, Media, MediaEpisode, User
from app.auth import get_current_user

router = APIRouter(prefix="/api", tags=["history"])

MAX_HISTORY = 20


@router.post("/history")
async def add_to_history(
    media_id: str,
    media_type: str,
    episode_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user_id = current_user.id
    now = datetime.now().isoformat()

    existing = (
        db.query(WatchHistory)
        .filter(
            WatchHistory.user_id == current_user_id,
            WatchHistory.media_id == media_id,
        )
        .first()
    )

    if existing:
        existing.last_episode = episode_number
        existing.updated_at = now

        watched_list = json.loads(existing.watched_episodes or "[]")
        if episode_number not in watched_list:
            watched_list.append(episode_number)
        existing.watched_episodes = json.dumps(watched_list)
    else:
        new_entry = WatchHistory(
            user_id=current_user_id,
            media_id=media_id,
            media_type=media_type,
            last_episode=episode_number,
            watched_episodes=json.dumps([episode_number]),
            updated_at=now,
        )
        db.add(new_entry)

    db.commit()

    # Garbage collector: mantém máximo de 20 registros
    count = (
        db.query(WatchHistory).filter(WatchHistory.user_id == current_user_id).count()
    )
    if count > MAX_HISTORY:
        old_entries = (
            db.query(WatchHistory)
            .filter(WatchHistory.user_id == current_user_id)
            .order_by(WatchHistory.updated_at.asc())
            .limit(count - MAX_HISTORY)
            .all()
        )
        for entry in old_entries:
            db.delete(entry)
        db.commit()

    return {"status": "ok"}


@router.get("/history")
async def get_history(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna o histórico de visualização (máx 20 itens).
    Re-valida disponibilidade em background quando passam 30 dias.
    """
    current_user_id = current_user.id
    entries = (
        db.query(WatchHistory)
        .filter(WatchHistory.user_id == current_user_id)
        .order_by(WatchHistory.updated_at.desc())
        .limit(MAX_HISTORY)
        .all()
    )

    result = []
    items_for_revalidation = []

    for entry in entries:
        clean_id = entry.media_id.replace("mal_", "").replace("tmdb_", "")
        media = db.query(Media).filter(Media.external_id == clean_id).first()

        result.append(
            {
                "media_id": entry.media_id,
                "media_type": entry.media_type,
                "last_episode": entry.last_episode,
                "watched_episodes": json.loads(entry.watched_episodes or "[]"),
                "updated_at": entry.updated_at,
                "title": media.title if media else "Desconhecido",
                "poster_url": media.poster_url if media else None,
            }
        )

        # Verificar se precisa de revalidação (Task 5)
        if media and entry.media_type == "anime":
            needs_check = True
            if media.last_verified:
                try:
                    last_dt = datetime.fromisoformat(media.last_verified)
                    needs_check = last_dt < datetime.utcnow() - timedelta(days=30)
                except Exception:
                    pass
            if needs_check:
                mal_id_str = clean_id
                items_for_revalidation.append(mal_id_str)

    if items_for_revalidation:
        # Usar asyncio.create_task para rodar em background (sem bloquear)
        asyncio.create_task(_revalidate_history_media(items_for_revalidation))

    return result


async def _revalidate_history_media(external_ids: list) -> None:
    """
    Task 5: Verifica disponibilidade dos animes do histórico em background.
    Atualiza `last_verified` e `available` no banco de dados.
    """
    from app.database import SessionLocal
    from app.models import Media
    from app.services.scraper import resolve_provider_slug

    db = SessionLocal()
    try:
        for ext_id in external_ids:
            if not ext_id.isdigit():
                continue
            mal_id = int(ext_id)
            try:
                slug = await resolve_provider_slug(mal_id)
                is_available = slug is not None
            except Exception:
                is_available = False

            media = db.query(Media).filter(Media.external_id == ext_id).first()
            if media:
                media.last_verified = datetime.utcnow().isoformat()
                media.available = is_available
                db.commit()
                print(f"[History Lazy] MAL {mal_id} — disponível={is_available}")
    except Exception as e:
        print(f"[History Lazy Revalidation] Erro: {e}")
    finally:
        db.close()


@router.get("/history/{media_id}")
async def get_history_for_media(
    media_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna os episódios assistidos de uma mídia específica.
    """
    current_user_id = current_user.id
    entry = (
        db.query(WatchHistory)
        .filter(
            WatchHistory.user_id == current_user_id,
            WatchHistory.media_id == media_id,
        )
        .first()
    )

    if not entry:
        return {"watched_episodes": [], "last_episode": 0}

    return {
        "watched_episodes": json.loads(entry.watched_episodes or "[]"),
        "last_episode": entry.last_episode,
    }
