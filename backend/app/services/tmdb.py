import os
import asyncio
import re
from typing import List, Dict, Any, Optional

from app.core.http_client import get_http_client
from app.utils.filters import is_japanese_content, JP_REGEX

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMG_ORIGINAL = "https://image.tmdb.org/t/p/original"
TMDB_IMG_W500 = "https://image.tmdb.org/t/p/w500"

# ─── Season / title helpers ───────────────────────────────────────────────────

_RE_SEASON_SUFFIX = re.compile(
    r"(?i)(\s*(?:\d+(?:st|nd|rd|th)?)?\s*season\s*\d*|\s*part\s*\d+|\s*cour\s*\d+)"
)
_SEASON_PATTERNS = [
    re.compile(r"(\d+)(?:st|nd|rd|th)?\s*season", re.IGNORECASE),
    re.compile(r"season\s*(\d+)", re.IGNORECASE),
    re.compile(r"part\s*(\d+)", re.IGNORECASE),
    re.compile(r"cour\s*(\d+)", re.IGNORECASE),
]


def extract_season_and_clean_title(title: str) -> tuple[str, int]:
    """
    Extrai o número da temporada do título e limpa o título para busca no TMDB.

    Examples:
        "Sousou no Frieren 2nd Season" → ("Sousou no Frieren", 2)
        "One Piece Season 22" → ("One Piece", 22)
        "Attack on Titan" → ("Attack on Titan", 1)
    """
    season_number = 1
    for pattern in _SEASON_PATTERNS:
        match = pattern.search(title)
        if match:
            season_number = int(match.group(1))
            break

    cleaned = _RE_SEASON_SUFFIX.sub("", title).strip()
    return cleaned, season_number


async def search_tmdb_by_title(
    title: str,
    title_english: Optional[str] = None,
    mal_id: Optional[int] = None,
    year: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Busca anime no TMDB pelo título com múltiplas tentativas.
    Retorna dados enriquecidos em pt-BR ou None se não encontrar.
    """
    # Debug logs removed for production
    if not TMDB_API_KEY or not title:
        return None

    cleaned_title, season_number = extract_season_and_clean_title(title)
    # Debug logs removed for production

    search_titles = []
    search_titles.append(title)
    if cleaned_title != title:
        search_titles.append(cleaned_title)
    if title_english and title_english != title and title_english != cleaned_title:
        search_titles.append(title_english)

    # Debug logs removed for production

    client = get_http_client()
    for search_query in search_titles:
        try:
            # Debug logs removed for production
            response = await client.get(
                f"{TMDB_BASE_URL}/search/tv",
                params={
                    "api_key": TMDB_API_KEY,
                    "query": search_query,
                    "language": "pt-BR",
                    "include_adult": "false",
                },
            )
            if response.status_code != 200:
                continue

            results = response.json().get("results", [])
            if not results:
                continue

            # Debug logs removed for production

            best_match = None
            for item in results:
                genres = item.get("genre_ids", [])
                origins = item.get("origin_country", [])
                if 16 in genres or "JP" in origins:
                    best_match = item
                    break
            if not best_match:
                best_match = results[0]

            tmdb_id = best_match.get("id")
            if not tmdb_id:
                continue

            # Debug logs removed for production

            final_season_number = season_number
            if year:
                details_resp = await client.get(
                    f"{TMDB_BASE_URL}/tv/{tmdb_id}",
                    params={"api_key": TMDB_API_KEY, "language": "pt-BR"},
                )
                if details_resp.status_code == 200:
                    for season in details_resp.json().get("seasons", []):
                        air_date = season.get("air_date")
                        s_num = season.get("season_number", 0)
                        if air_date and s_num > 0:
                            try:
                                s_year = int(air_date.split("-")[0])
                                if abs(s_year - year) <= 1:
                                    final_season_number = s_num

                                    # Debug logs removed for production
                                    break
                            except (ValueError, IndexError):
                                pass

            # Debug logs removed for production

            # Busca dados da temporada e da série em paralelo
            season_resp, series_resp = await asyncio.gather(
                client.get(
                    f"{TMDB_BASE_URL}/tv/{tmdb_id}/season/{final_season_number}",
                    params={"api_key": TMDB_API_KEY, "language": "pt-BR"},
                ),
                client.get(
                    f"{TMDB_BASE_URL}/tv/{tmdb_id}",
                    params={"api_key": TMDB_API_KEY, "language": "pt-BR"},
                ),
            )

            season_data = season_resp.json() if season_resp.status_code == 200 else None
            series_data = series_resp.json() if series_resp.status_code == 200 else {}

            result = {
                "tmdb_id": tmdb_id,
                "season_number": final_season_number,
                "title": series_data.get("name") or best_match.get("name"),
                "synopsis": (
                    (season_data or {}).get("overview")
                    or series_data.get("overview")
                    or best_match.get("overview")
                ),
                "poster_path": (
                    (season_data or {}).get("poster_path")
                    or series_data.get("poster_path")
                    or best_match.get("poster_path")
                ),
                "backdrop_path": (
                    (season_data or {}).get("backdrop_path")
                    or series_data.get("backdrop_path")
                    or best_match.get("backdrop_path")
                ),
                "vote_average": series_data.get("vote_average")
                or best_match.get("vote_average"),
                "season_data": season_data,
            }

            # Debug logs removed for production
            return result

        except Exception:
            continue

    return None


async def get_tmdb_episodes(
    tmdb_id: int, season_number: int = 1, season_data: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Busca episódios de uma série no TMDB em pt-BR.
    Se season_data for passado, usa diretamente (evita chamada extra).
    """
    if not TMDB_API_KEY:
        return []

    if season_data and season_data.get("episodes"):
        return [
            {
                "episode_number": ep.get("episode_number"),
                "title": ep.get("name"),
                "synopsis": ep.get("overview"),
                "still_path": ep.get("still_path"),
            }
            for ep in season_data.get("episodes", [])
            if ep.get("episode_number")
        ]

    client = get_http_client()
    for attempt in range(3):
        try:
            response = await client.get(
                f"{TMDB_BASE_URL}/tv/{tmdb_id}/season/{season_number}",
                params={"api_key": TMDB_API_KEY, "language": "pt-BR"},
            )
            if response.status_code == 200:
                return [
                    {
                        "episode_number": ep.get("episode_number"),
                        "title": ep.get("name"),
                        "synopsis": ep.get("overview"),
                        "still_path": ep.get("still_path"),
                    }
                    for ep in response.json().get("episodes", [])
                    if ep.get("episode_number")
                ]
            return []
        except Exception as e:
            if attempt == 2:
                print(f"[TMDB] Erro ao buscar episódios TMDB {tmdb_id}: {e}")
                return []
            await asyncio.sleep(1)
    return []


async def search_tmdb(query: str) -> List[Dict[str, Any]]:
    """
    Busca filmes e séries no TMDB com RETRY.
    Filtra animes japoneses (JP) para evitar duplicatas com o Jikan,
    e filtra filmes irrelevantes (baixa popularidade/não-animação).
    """
    if not TMDB_API_KEY:
        return []

    client = get_http_client()
    for attempt in range(3):
        try:
            response = await client.get(
                f"{TMDB_BASE_URL}/search/multi",
                params={
                    "api_key": TMDB_API_KEY,
                    "query": query,
                    "language": "pt-BR",
                    "include_adult": "false",
                },
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", []):
                # 1. Filtro do Jikan (Evita animes duplicados)
                if is_japanese_content(item):
                    print(
                        f"[TMDB Filter] Bloqueado (JP/JA): {item.get('name') or item.get('title')}"
                    )
                    continue

                media_type = item.get("media_type")
                if media_type not in ["movie", "tv"]:
                    continue

                # -------------------------------------------------------------
                # 2. A PENEIRA DE FILMES (Nova Regra!)
                # -------------------------------------------------------------
                if media_type == "movie":
                    votos = item.get("vote_count", 0)
                    generos = item.get("genre_ids", [])

                    is_animacao = 16 in generos
                    is_famoso = votos > 50  # Corta curtas-metragens e filmes amadores

                    if not (is_animacao or is_famoso):
                        # Se não for animação e ninguém votou, descarta!
                        continue
                # -------------------------------------------------------------

                results.append(
                    {
                        "id": item.get("id"),
                        "tmdb_id": item.get("id"),
                        "title": item.get("title") or item.get("name"),
                        "synopsis": item.get("overview"),
                        "poster_url": f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}"
                        if item.get("poster_path")
                        else None,
                        "media_type": "movie" if media_type == "movie" else "tv",
                        "year": (
                            item.get("release_date") or item.get("first_air_date") or ""
                        )[:4],
                    }
                )

            return results
        except Exception as e:
            print(f"[TMDB] Erro na busca (tentativa {attempt + 1}): {e}")
            if attempt == 2:
                return []
            await asyncio.sleep(1)
    return []


async def get_tmdb_details(
    tmdb_id: int, initial_media_type: str = "tv"
) -> Dict[str, Any]:
    """
    Busca detalhes no TMDB com RETRY. Tenta TV primeiro, com fallback para Movie.
    """
    if not TMDB_API_KEY:
        return {}

    client = get_http_client()

    async def _fetch(m_type: str) -> Optional[Dict[str, Any]]:
        for attempt in range(3):
            try:
                response = await client.get(
                    f"{TMDB_BASE_URL}/{m_type}/{tmdb_id}",
                    params={"api_key": TMDB_API_KEY, "language": "pt-BR"},
                )
                if response.status_code == 200:
                    data = response.json()
                    data["media_type_actual"] = m_type
                    return data
                if response.status_code == 404:
                    return None
            except Exception as e:
                if attempt == 2:
                    break
                await asyncio.sleep(1)
        return None

    result = await _fetch("tv")
    if result:
        return result

    return await _fetch("movie") or {}
