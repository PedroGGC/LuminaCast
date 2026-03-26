from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserList, Media, User
from app.schemas import MyListResponse, MyListAdd
from app.auth import get_current_user

router = APIRouter(prefix="/api/my-list", tags=["user_list"])


@router.get("", response_model=list[MyListResponse])
def get_my_list(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return all medias saved by the current user."""
    items = (
        db.query(UserList)
        .filter(UserList.user_id == current_user.id, UserList.media_id.isnot(None))
        .all()
    )
    return items


from app.services.sync_service import sync_media_by_id

@router.post("", response_model=MyListResponse, status_code=status.HTTP_201_CREATED)
async def add_to_list(item_in: MyListAdd, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a media (anime or cartoon) to the user's list."""
    media_id_str = str(item_in.media_id)
    media_type = None

    if media_id_str.startswith("mal_"):
        media_type = "anime"
        media_id_str = media_id_str.replace("mal_", "")
    elif media_id_str.startswith("tmdb_"):
        media_type = "desenho"
        media_id_str = media_id_str.replace("tmdb_", "")

    media = None
    if media_id_str.isdigit():
        media = db.query(Media).filter((Media.id == int(media_id_str)) | (Media.external_id == media_id_str)).first()
    else:
        media = db.query(Media).filter(Media.external_id == media_id_str).first()

    if not media and not media_type and media_id_str.isdigit():
        from app.models import AnimeMapping
        is_seeded_anime = db.query(AnimeMapping).filter(AnimeMapping.mal_id == int(media_id_str)).first()
        if is_seeded_anime:
            media_type = "anime"

    if not media:
        media = await sync_media_by_id(media_id_str, media_type, db)
        if not media:
            raise HTTPException(status_code=404, detail="Mídia não encontrada nas APIs externas")
        db.commit()
        db.expire_all()
        # Recarrega do banco
        media = db.query(Media).filter(Media.id == media.id).first()

    existing = db.query(UserList).filter(
        UserList.user_id == current_user.id,
        UserList.media_id == media.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Título já está na sua lista")

    new_item = UserList(user_id=current_user.id, media_id=media.id)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_list(media_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Remove a media from the user's list."""
    media_id_str = str(media_id)
    
    if media_id_str.startswith("mal_"):
        media_id_str = media_id_str.replace("mal_", "")
    elif media_id_str.startswith("tmdb_"):
        media_id_str = media_id_str.replace("tmdb_", "")

    media = None
    if media_id_str.isdigit():
        media = db.query(Media).filter((Media.id == int(media_id_str)) | (Media.external_id == media_id_str)).first()
    else:
        media = db.query(Media).filter(Media.external_id == media_id_str).first()

    if not media:
        raise HTTPException(status_code=404, detail="Item não encontrado na sua lista")

    item = db.query(UserList).filter(
        UserList.user_id == current_user.id,
        UserList.media_id == media.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado na sua lista")

    db.delete(item)
    db.commit()
    return None
