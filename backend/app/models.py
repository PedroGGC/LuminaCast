from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    Text,
    Float,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)

    my_list = relationship(
        "UserList", back_populates="user", cascade="all, delete-orphan"
    )


class UserList(Base):
    __tablename__ = "user_list"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    anime_id = Column(Integer, ForeignKey("animes.id"), nullable=True)
    media_id = Column(Integer, ForeignKey("media.id"), nullable=True)

    user = relationship("User", back_populates="my_list")
    anime = relationship("Anime", foreign_keys=[anime_id])
    media = relationship("Media", foreign_keys=[media_id])


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    slug = Column(String(100), nullable=False, unique=True)

    animes = relationship("Anime", back_populates="category", lazy="selectin")


class Anime(Base):
    __tablename__ = "animes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    synopsis = Column(Text, nullable=True)
    cover_image = Column(String(500), nullable=True)
    banner_image = Column(String(500), nullable=True)
    rating = Column(Float, default=0.0)
    year = Column(Integer, nullable=True)
    content_type = Column(String(50), default="anime")  # "anime" or "cartoon"
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    category = relationship("Category", back_populates="animes")
    episodes = relationship("Episode", back_populates="anime", lazy="selectin")


class Episode(Base):
    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    thumbnail = Column(String(500), nullable=True)
    stream_url = Column(String(1000), nullable=True)
    anime_id = Column(Integer, ForeignKey("animes.id"), nullable=False)

    anime = relationship("Anime", back_populates="episodes")


class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(100), index=True)
    title = Column(String(255), nullable=False)
    original_title = Column(String(255), nullable=True)
    synopsis = Column(Text, nullable=True)
    poster_url = Column(String(500), nullable=True)
    backdrop_url = Column(String(500), nullable=True)
    media_type = Column(String(50))  # "anime" ou "desenho"
    #campos de verificação de disponibilidade
    last_verified = Column(String(50), nullable=True)   # ISO datetime string
    available = Column(Boolean, default=True, nullable=False)

    episodes = relationship(
        "MediaEpisode", back_populates="media", cascade="all, delete-orphan"
    )


class MediaEpisode(Base):
    __tablename__ = "media_episodes"

    id = Column(Integer, primary_key=True, index=True)
    media_id = Column(Integer, ForeignKey("media.id"), nullable=False)
    season_number = Column(Integer, default=1)
    episode_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    video_url = Column(String(1000), nullable=True)  # URL cacheada do stream

    media = relationship("Media", back_populates="episodes")

    __table_args__ = (
        UniqueConstraint(
            "media_id", "season_number", "episode_number", name="uix_media_episode"
        ),
    )


class AnimeMapping(Base):
    __tablename__ = "anime_mappings"

    id = Column(Integer, primary_key=True, index=True)
    mal_id = Column(Integer, index=True)
    animefire_slug = Column(String(255))


class JikanCache(Base):
    __tablename__ = "jikan_cache"

    id = Column(Integer, primary_key=True, index=True)
    request_url = Column(String(500), unique=True, index=True)
    response_json = Column(Text)
    created_at = Column(
        String(50)
    )  # Simplificado para String para evitar complexidade de DateTime em SQLite


class WatchHistory(Base):
    __tablename__ = "watch_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    media_id = Column(String(100), nullable=False)  # "mal_59978" ou TMDB ID
    media_type = Column(String(50), nullable=False)  # "anime", "movie", "tv"
    last_episode = Column(Integer, default=0)
    watched_episodes = Column(String(500), default="[]")  # JSON string list
    updated_at = Column(String(50))

    __table_args__ = (
        UniqueConstraint("user_id", "media_id", name="uix_user_media_history"),
    )


class ApiCache(Base):
    """Cache híbrido de resultados de busca no banco de dados (TTL: 7 dias)."""
    __tablename__ = "api_cache"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String(500), unique=True, index=True, nullable=False)
    result_json = Column(Text, nullable=True)
    available_data = Column(Text, nullable=True)
    verified_at = Column(String(50), nullable=True)
    expires_at = Column(String(50), nullable=True)
