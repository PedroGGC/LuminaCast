from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    nome: str
    email: EmailStr


class UserCreate(UserBase):
    senha: str


class UserLogin(BaseModel):
    email: EmailStr
    senha: str


class UserOut(UserBase):
    id: int

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: str | None = None


class EpisodeOut(BaseModel):
    id: int
    number: int
    title: str | None = None
    thumbnail: str | None = None
    stream_url: str | None = None

    model_config = {"from_attributes": True}


class AnimeOut(BaseModel):
    id: int
    title: str
    synopsis: str | None = None
    cover_image: str | None = None
    banner_image: str | None = None
    rating: float
    year: int | None = None
    content_type: str

    model_config = {"from_attributes": True}


class AnimeDetailOut(AnimeOut):
    episodes: list[EpisodeOut] = []


class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    animes: list[AnimeOut] = []

    model_config = {"from_attributes": True}


class UserListAdd(BaseModel):
    anime_id: int


class UserListResponse(BaseModel):
    id: int
    user_id: int
    anime_id: int
    anime: AnimeOut

    model_config = {"from_attributes": True}


class MediaOut(BaseModel):
    id: int
    external_id: str | None = None
    title: str
    synopsis: str | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None
    media_type: str | None = None

    model_config = {"from_attributes": True}


class MediaEpisodeOut(BaseModel):
    id: int
    media_id: int
    season_number: int
    episode_number: int
    title: str | None = None
    thumbnail_url: str | None = None

    model_config = {"from_attributes": True}


class MyListAdd(BaseModel):
    media_id: str | int


class MyListResponse(BaseModel):
    id: int
    user_id: int
    media_id: int
    media: MediaOut

    model_config = {"from_attributes": True}
