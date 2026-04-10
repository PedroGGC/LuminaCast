"""
Motor de Extração Definitivo (Scraper Service)

Responsabilidades:
- Busca precisa usando original_title (japonês/inglês original).
- Regras heurísticas para achar a Temporada correta e priorizar Dublado.
- Ajuste de rotas do provider (/animes/ -> /video/).
- Extração segura do JSON via data-video-url e fallback garantido.
"""

import re
import httpx
import logging
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

logger = logging.getLogger("scraper")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)
from app.utils import slugify
from app.services.anime_offline_db import (
    get_anime_by_mal_id,
    get_anime_type,
    get_search_terms,
)
from app.database import SessionLocal
from app.models import AnimeMapping

# ─── Regex compilados uma única vez no startup ─────────────────────────────────

_RE_SEQUEL = re.compile(
    r"\b(shimetsu|kaiyuu|kaigyoku|gyokusetsu|zenpen|kouhen|"
    r"2nd|3rd|4th|\d+th|season[\-\s]*\d+|part[\-\s]*\d+|"
    r"cour[\-\s]*\d+|movie|filme|film|ova|ona|special|especial)\b",
    re.IGNORECASE,
)

_RE_SLUG_CLEAN = re.compile(
    r"-(todos-os-episodios|all-episodes|dublado|legendado|ptbr|pt-br)$"
)
_RE_SEASON_NUMS = re.compile(r"\d+")

# Padrões de extração do Blogger
_RE_BLOGGER_RAW = re.compile(
    r"(https?[^\s\"'<>]*?(?:googlevideo\.com|blogger\.com|video\.google\.com)"
    r"[^\s\"'<>]*?videoplayback[^\s\"'<>]*?)"
)
_RE_BLOGGER_ENCODED = re.compile(
    r"(https%3A%2F%2F[^\s\"'<>]*?videoplayback[^\s\"'<>]*?)"
)
_RE_BLOGGER_WIZ = re.compile(r"window\.WIZ_global_data\s*=\s*(\{.+?\});", re.DOTALL)
_RE_BLOGGER_FALLBACK = re.compile(
    r'"(?:play_url|videoUrl|contentUrl|streamUrl)"\s*:\s*"([^"]+)"'
)
_RE_SOURCE_TAG = re.compile(r'<source[^>]+src="([^"]+)"')


def _get_best_quality_url(urls: list[str]) -> str | None:
    """
    Prioriza URLs por qualidade baseado no itag:
    - itag=37: 1080p (prioridade máxima)
    - itag=22: 720p
    - itag=18: 360p (menor)
    """
    if not urls:
        return None

    best_url = urls[0]
    highest_score = 0

    for url in urls:
        if "itag=37" in url:
            return url
        elif "itag=22" in url:
            if highest_score < 2:
                best_url = url
                highest_score = 2
        elif "itag=18" in url:
            if highest_score < 1:
                best_url = url
                highest_score = 1

    return best_url


# ─── Cache Global de Slugs ─────────────────────────────────────────────────────

SLUG_CACHE: dict[str, str] = {}


def get_cached_slug(mal_id: int) -> str | None:
    return SLUG_CACHE.get(str(mal_id))


def set_cached_slug(mal_id: int, slug: str) -> None:
    SLUG_CACHE[str(mal_id)] = slug


# ─── Constantes ────────────────────────────────────────────────────────────────

HLS_FALLBACK_URL = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Connection": "keep-alive",
    "Referer": "https://animefire.io/",
}


# ─── Scoring helpers ──────────────────────────────────────────────────────────


def _extract_slug_name(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    slug = _RE_SLUG_CLEAN.sub("", slug)
    return slug.replace("-", " ").strip()


def _score_slug_candidate(
    url: str, target_title: str, mal_id: int | None = None
) -> float:
    slug_clean = _extract_slug_name(url)
    target_norm = target_title.lower().strip()

    similarity = SequenceMatcher(None, slug_clean, target_norm).ratio()

    target_is_sequel = bool(
        re.search(r"(2nd|3rd|4th|\d+th|season|part|cour|movie|filme)", target_norm)
    )

    if target_is_sequel:
        if _RE_SEQUEL.search(url):
            similarity *= 1.3
    else:
        if _RE_SEQUEL.search(url):
            similarity *= 0.35

    anime_type = get_anime_type(mal_id) if mal_id else "UNKNOWN"
    if anime_type == "TV" and re.search(r"[\-]tv[\-]|[\-]tv$", url.split("/")[-1]):
        similarity *= 1.25

    slug_word_count = len(slug_clean.split())
    target_word_count = len(target_norm.split())
    if slug_word_count > target_word_count * 2.5:
        similarity *= 0.6

    return min(round(similarity, 4), 1.0)


def _pick_best_slug(
    candidates: list[str],
    mal_title: str,
    mal_id: int | None = None,
    prefer_dubbed: bool = True,
    min_score: float = 0.2,
    season_hint: int = None,
) -> str | None:
    if not candidates:
        return None

    if season_hint:
        filtered = []
        for c in candidates:
            if _is_valid_season(c, season_hint):
                filtered.append(c)
        candidates = filtered
        if not candidates:
            return None

    if mal_title:
        target_title = mal_title
        filtered = []
        for c in candidates:
            if _reject_spinoffs(c, target_title):
                continue
            filtered.append(c)
        candidates = filtered
        if not candidates:
            return None

    scored = [
        (url, _score_slug_candidate(url, mal_title, mal_id)) for url in candidates
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    best_score = scored[0][1]
    if best_score < min_score:
        return None

    if prefer_dubbed:
        top = [(url, s) for url, s in scored if best_score - s < 0.15]
        dubbed = [(url, s) for url, s in top if "dublado" in url]
        if dubbed:
            dubbed.sort(key=lambda x: x[1], reverse=True)
            best_url = dubbed[0][0]
        else:
            best_url = scored[0][0]
    else:
        best_url = scored[0][0]

    return best_url


# ─── Utilitários de Heurística ───────────────────────────────────────────────


def _is_valid_season(title: str, season: int) -> bool:
    """Aplica regra de validação de temporada no título encontrado."""
    t_lower = title.lower()

    if season == 1:
        forbidden = [
            "2nd",
            "3rd",
            "4th",
            "5th",
            "6th",
            "season 2",
            "season 3",
            "season 4",
            "season 5",
            "season 6",
            "part 2",
            "2ª temporada",
            "3ª temporada",
            "movie",
            "filme",
            "ova",
        ]
        return not any(f in t_lower for f in forbidden)
    else:
        if str(season) in t_lower:
            return True
        nums = _RE_SEASON_NUMS.findall(t_lower)
        return str(season) in nums


def _reject_spinoffs(title: str, target_title: str) -> bool:
    """Heurística para evitar resolver spin-offs.

    Ex: "Boku no Hero Academia" deve rejeitar "Vigilantes".
    """
    t = title.lower()
    target = (target_title or "").lower()

    spinoff_markers = [
        "vigilantes",
        "vigilante",
        "spin-off",
        "spin off",
        "prequel",
        "sequel",
        "side story",
    ]
    if any(m in t for m in spinoff_markers) and not any(
        m in target for m in spinoff_markers
    ):
        return True
    return False


def _extract_best_quality(data_list) -> str | None:
    if not isinstance(data_list, list) or not data_list:
        return None
    quality_map = {"1080p": 3, "720p": 2, "480p": 1, "360p": 0}
    sorted_list = sorted(
        data_list,
        key=lambda x: quality_map.get(str(x.get("label", "")).lower(), -1),
        reverse=True,
    )
    return sorted_list[0].get("src")


# ─── Extração do Blogger ─────────────────────────────────────────────────────


async def extract_from_blogger(url: str, client) -> str:
    """Tenta extrair o MP4 do Blogger. Se falhar, retorna a URL original (Iframe)."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://animefire.io/",
        }

        blogger_resp = await client.get(url, headers=headers, timeout=10.0)

        if blogger_resp.status_code == 200:
            best_video_url = extract_best_video_url(blogger_resp.text)
            if best_video_url:
                return best_video_url

        return url

    except Exception as e:
        logger.error(f"Erro na extração do Blogger: {e}", exc_info=True)
        return url


def extract_best_video_url(html_content: str) -> str | None:
    """
    Tenta extrair o MP4 direto do Google. Se falhar, retorna None
    para acionar a proteção de Iframe, sem quebrar o player.
    """
    import urllib.parse
    import re

    # Limpeza rápida e dupla decodificação (URL encoded)
    text = (
        html_content.replace("\\/", "/")
        .replace("\\u0026", "&")
        .replace("\\u003d", "=")
        .replace('\\"', '"')
    )
    text = urllib.parse.unquote(urllib.parse.unquote(text))

    # Busca o parâmetro videoplayback na URL
    urls = re.findall(
        r'(https://[^\s"\'<>\[\]\\]*?videoplayback[^\s"\'<>\[\]\\]*)', text
    )

    if not urls:
        return None

    valid_urls = []
    for u in urls:
        clean_u = u.split(",")[0].split("]")[0].split('"')[0].split("'")[0]
        if "videoplayback" in clean_u:
            valid_urls.append(clean_u)

    if not valid_urls:
        return None

    valid_urls = list(set(valid_urls))
    best_url = valid_urls[0]
    highest_score = -1

    for url in valid_urls:
        if "itag=37" in url:
            return url  # 1080pfixo (itag=37)
        elif "itag=22" in url:
            if highest_score < 2:
                best_url, highest_score = url, 2
        elif "itag=18" in url:
            if highest_score < 1:
                best_url, highest_score = url, 1

    return best_url


# ─── Descoberta de Candidatos ────────────────────────────────────────────────


def _sanitize_title(title: str) -> str:
    """Remove caracteres especiais de forma agressiva, mantendo apenas letras, números e espaços."""
    if not title:
        return ""
    clean = re.sub(r"[^\w\s]", " ", title)
    return re.sub(r"\s+", " ", clean).strip()


async def search_provider_candidates(term: str) -> list[str]:
    """Pesquisa um termo no provider e retorna lista de URLs de candidatos."""
    async with httpx.AsyncClient(headers=HEADERS, timeout=15.0) as client:
        slug = slugify(term)
        if not slug:
            return []
        try:
            resp = await client.get(f"https://animefire.io/pesquisar/{slug}")
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                found = soup.find_all("article") or soup.select(".row.ml-1.mr-1 a")
                urls = []
                for item in found:
                    a_tag = item.find("a", href=True) if item.name != "a" else item
                    if a_tag and "/animes/" in a_tag.get("href", ""):
                        urls.append(a_tag["href"])
                return urls
        except Exception:
            pass
    return []


async def search_provider_with_fallback(
    original_title: str,
    title_english: str | None = None,
) -> list[str]:
    """Pesquisa no provider com sanitização e fallback para título em inglês."""
    clean_title = _sanitize_title(original_title)
    candidates = await search_provider_candidates(clean_title)

    if not candidates and title_english:
        clean_english = _sanitize_title(title_english)
        candidates = await search_provider_candidates(clean_english)

    return candidates


async def resolve_provider_slug(
    mal_id: int, target_title: str = None, season_hint: int = None
) -> str | None:
    """Resolve o slug do provider para um MAL ID usando busca em cascata."""
    entry = get_anime_by_mal_id(mal_id)
    if not entry:
        return None

    main_title = target_title or entry["title"]
    title_english = entry.get("title_english")

    cache_key = str(mal_id)
    if cache_key in SLUG_CACHE:
        cached = SLUG_CACHE[cache_key]
        if season_hint and not _is_valid_season(cached, season_hint):
            del SLUG_CACHE[cache_key]
        else:
            return cached

    def generate_provider_slug(title: str) -> str:
        clean = title.lower()
        clean = re.sub(r"[^\w\s\-]", "", clean)
        return re.sub(r"\s+", "-", clean)

    guess_slug = generate_provider_slug(main_title)
    guess_urls = [
        f"https://animefire.io/animes/{guess_slug}-dublado-todos-os-episodios",
        f"https://animefire.io/animes/{guess_slug}-todos-os-episodios",
        f"https://animefire.io/animes/{guess_slug}-dublado",
    ]

    async with httpx.AsyncClient(
        headers=HEADERS, timeout=10.0, follow_redirects=True
    ) as guess_client:
        for guess_url in guess_urls:
            try:
                guess_resp = await guess_client.get(guess_url)
                if (
                    guess_resp.status_code == 200
                    and "Página não encontrada" not in guess_resp.text
                ):
                    if season_hint and not _is_valid_season(
                        str(guess_resp.url), season_hint
                    ):
                        continue
                    if "animefire" in str(guess_resp.url):
                        final_url = str(guess_resp.url)
                        SLUG_CACHE[cache_key] = final_url
                        set_cached_slug(mal_id, final_url.split("/")[-1])
                        return final_url
            except Exception as e:
                pass

    clean_original = _sanitize_title(main_title)
    clean_english = _sanitize_title(title_english) if title_english else ""

    search_queries = [clean_original]
    if clean_english and clean_english != clean_original:
        search_queries.append(clean_english)
    short_query = " ".join(clean_original.split()[:2])
    if short_query and len(short_query) >= 3 and short_query not in search_queries:
        search_queries.append(short_query)

    all_candidates: list[str] = []
    seen: set[str] = set()

    for query in search_queries:
        if not query or len(query) < 2:
            continue
        results = await search_provider_candidates(query)
        if results:
            for c in results:
                if c not in seen:
                    seen.add(c)
                    all_candidates.append(c)
            break

    if not all_candidates:
        search_terms = get_search_terms(mal_id)
        for term in search_terms[:3]:
            safe_term = _sanitize_title(term)
            if safe_term and safe_term not in seen:
                results = await search_provider_candidates(safe_term)
                if results:
                    for c in results:
                        if c not in seen:
                            seen.add(c)
                            all_candidates.append(c)
                    break

    if not all_candidates:
        return None

    best = _pick_best_slug(
        all_candidates,
        main_title,
        mal_id=mal_id,
        prefer_dubbed=True,
        season_hint=season_hint,
    )

    if best and "animefire" in best:
        SLUG_CACHE[cache_key] = best
        set_cached_slug(mal_id, best.split("/")[-1] if "/" in best else best)

    return best


# ─── Motor Específico do Provider ───────────────────────────────────────────────


async def _scrape_provider(
    title: str,
    original_title: str,
    season: int,
    episode_number: int,
    mal_id: int = None,
    cached_slug: str = None,
) -> str:
    """Executa a extração de URL do episódio via provider."""
    try:
        async with httpx.AsyncClient(
            headers=HEADERS, follow_redirects=True, timeout=20.0
        ) as client:
            candidatos = []

            if cached_slug:
                candidatos = [{"url": f"/animes/{cached_slug}"}]

            if mal_id and not candidatos:
                db = SessionLocal()
                mapping = (
                    db.query(AnimeMapping).filter(AnimeMapping.mal_id == mal_id).first()
                )
                db.close()
                if mapping:
                    candidatos = [{"url": f"/animes/{mapping.animefire_slug}"}]

            if not candidatos:
                final_url = (
                    await resolve_provider_slug(mal_id, season_hint=season)
                    if mal_id
                    else None
                )
                if not final_url:
                    return HLS_FALLBACK_URL
                candidatos = [{"url": final_url}]

            for candidato in candidatos:
                winner_href = candidato["url"]

                if not winner_href.startswith("http"):
                    if not winner_href.startswith("/"):
                        winner_href = f"/animes/{winner_href}"
                    winner_href = f"https://animefire.io{winner_href}"

                video_base_url = winner_href.replace("-todos-os-episodios", "").replace(
                    "/animes/", "/video/"
                )
                episode_url = f"{video_base_url}/{episode_number}"

                try:
                    ep_resp = await client.get(episode_url)

                    if ep_resp.status_code != 200:
                        continue

                    try:
                        data = ep_resp.json()
                        token = data.get("token")
                        if (
                            token
                            and isinstance(token, str)
                            and token.startswith("http")
                        ):
                            return await extract_from_blogger(token, client)
                        if "data" in data:
                            best_url = _extract_best_quality(data.get("data"))
                            if best_url:
                                return best_url
                    except Exception:
                        pass

                    ep_soup = BeautifulSoup(ep_resp.text, "html.parser")
                    video_element = ep_soup.find(attrs={"data-video-url": True})

                    if not video_element:
                        continue

                    video_json_url = video_element.get("data-video-url")
                    json_resp = await client.get(video_json_url)

                    data = json_resp.json()
                    token = data.get("token")

                    if token and isinstance(token, str) and token.startswith("http"):
                        return await extract_from_blogger(token, client)

                    if "data" in data:
                        best_url = _extract_best_quality(data.get("data"))
                        if best_url:
                            return best_url

                except Exception:
                    continue

            return HLS_FALLBACK_URL

    except Exception as e:
        logger.error(f"Erro crítico no _scrape_provider: {e}", exc_info=True)
        return HLS_FALLBACK_URL


async def list_provider_episodes(slug: str) -> list[int]:
    """Retorna a lista de números de episódios disponíveis no provider para um slug."""
    url = f"https://animefire.io/animes/{slug}"
    async with httpx.AsyncClient(headers=HEADERS, timeout=15.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")

                # 1. Tentativa: Extrair total de episódios via metadados ou texto
                # Procura texto como "474 episodios" ou "474 episodes" na página
                # Padrão: número seguido por "episódios" ou "episodes"
                pattern = r"(\d+)\s+(?:episódios|episodes)"
                match = re.search(pattern, text_content)
                if match:
                    total_eps = int(match.group(1))
                    # Gera URLs diretamente: 1, 2, 3, ..., total_eps
                    return list(range(1, total_eps + 1))

                # 2. Tentativa: Extrair máximo via dropdown
                episode_selector = soup.select_one("select[name='episodes']")
                if episode_selector:
                    options = episode_selector.select("option")
                    numbers = []
                    for opt in options:
                        val = opt.get("value", "")
                        match = re.search(r"/(\d+)$", val)
                        if match:
                            numbers.append(int(match.group(1)))
                    if numbers:
                        return sorted(set(numbers))

                # 3. Tentativa: Extrair de links visíveis na página
                ep_links = soup.select(".div_video_list a")
                visible_numbers = []
                for link in ep_links:
                    href = link.get("href", "")
                    match = re.search(r"/(\d+)$", href)
                    if match:
                        visible_numbers.append(int(match.group(1)))

                if visible_numbers:
                    return sorted(set(visible_numbers))

                # 4. Fallback: Lista padrão para animes populares
                # Se não encontramos metadados, verificar se é um anime popular
                # Para One Piece e Frieren, sabemos que têm muitos episódios
                popular_slugs = [
                    "one-piece",
                    "one-piece-dublado",
                    "sousou-no-frieren",
                    "sousou-no-frieren-dublado",
                ]
                for popular in popular_slugs:
                    if slug.startswith(popular):
                        # One Piece tem 474 eps (atual), Frieren S1 tem 28
                        if "one-piece" in slug:
                            return list(range(1, 475))  # 474 episódios
                        elif "frieren" in slug:
                            return list(range(1, 29))  # 28 episódios

                return []
        except Exception:
            pass
    return []


# ─── Função Pública de Entrada ───────────────────────────────────────────────


async def extract_episode_url(
    external_id: str,
    title: str,
    original_title: str,
    season: int,
    episode: int,
    media_type: str,
    cached_slug: str = None,
) -> str:
    """
    Roteador de Scrapers:
    - Se for Anime: Tenta scraper local, se falhar usa Cloudflare Worker.
    - Se for Desenho/Filme: Retorna fallback (HLS de teste).
    """
    if media_type == "anime":
        mal_id = int(external_id) if external_id and external_id.isdigit() else None

        # Usa a rota /resolve que faz tudo: busca + retorna URL do episódio
        from app.services.cloudflare_worker import resolve_episode_url

        # Normaliza o título para minúsculas e remove caracteres especiais
        import re

        normalized_title = title.lower().strip() if title else ""
        normalized_title = re.sub(r"[^\w\s\-]", "", normalized_title)
        normalized_title = re.sub(r"\s+", " ", normalized_title).strip()

        logger.info(
            f"[Stream] MAL_ID: {mal_id}, Título: '{normalized_title}', Episódio: {episode}"
        )

        # Tenta dublado primeiro
        video_url = await resolve_episode_url(
            normalized_title, episode, prefer_dubbed=True
        )

        if video_url != HLS_FALLBACK_URL:
            logger.info(f"[Stream] Sucesso com dublado: {video_url[:80]}...")
            return video_url

        # Tenta legendado
        logger.info("[Stream] Tentando versão legendado...")
        video_url = await resolve_episode_url(
            normalized_title, episode, prefer_dubbed=False
        )

        if video_url != HLS_FALLBACK_URL:
            logger.info(f"[Stream] Sucesso com legendado: {video_url[:80]}...")
            return video_url

        logger.warning(f"[Stream] Fallback ativado para '{normalized_title}'")
        return video_url

    return HLS_FALLBACK_URL
