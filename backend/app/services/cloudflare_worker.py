"""
Cloudflare Worker Proxy Service

Faz a ponte entre o backend e o Cloudflare Worker que scrapeia o AnimeFire.
"""

import httpx
import urllib.parse
import logging

logger = logging.getLogger("cloudflare_worker")

WORKER_URL = "https://luminacast.pedroogabrielg.workers.dev"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

HLS_FALLBACK = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"


async def get_episode_url_from_worker(episode_url: str) -> str:
    """
    Chama o Cloudflare Worker para obter a URL do vídeo.

    Args:
        episode_url: URL do episódio no AnimeFire (ex: https://animefire.io/video/naruto-dublado/1)

    Returns:
        URL direta do vídeo (.mp4 ou .m3u8), ou fallback em caso de erro.
    """
    try:
        encoded_url = urllib.parse.quote(episode_url, safe="")
        worker_url = f"{WORKER_URL}/watch?url={encoded_url}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(worker_url, headers=HEADERS)

            if response.status_code == 200:
                data = response.json()

                if data.get("success") and data.get("video_url"):
                    video_url = data["video_url"]
                    logger.info(f"Worker retornou URL: {video_url[:80]}...")
                    return video_url
                else:
                    logger.warning(f"Worker retornou erro: {data.get('error')}")
            else:
                logger.warning(f"Worker retornou status {response.status_code}")

    except Exception as e:
        logger.error(f"Erro ao chamar Cloudflare Worker: {e}")

    return HLS_FALLBACK


async def search_anime_from_worker(query: str) -> list[dict]:
    """
    Busca anime via Cloudflare Worker.

    Args:
        query: Termo de busca

    Returns:
        Lista de resultados com 'url', 'slug' e 'title'
    """
    try:
        worker_url = f"{WORKER_URL}/search?q={query}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(worker_url, headers=HEADERS)

            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])

    except Exception as e:
        logger.error(f"Erro na busca via Worker: {e}")

    return []


async def find_anime_slug(title: str, prefer_dubbed: bool = True) -> str | None:
    """
    Busca o slug correto do anime no AnimeFire.

    Args:
        title: Título do anime
        prefer_dubbed: Preferir versão dublada

    Returns:
        Slug do anime (ex: sousou-no-frieren-dublado) ou None se não encontrar
    """
    results = await search_anime_from_worker(title)

    if not results:
        return None

    # Primeiro tenta encontrar correspondência no título
    title_lower = title.lower()

    for result in results:
        result_title = result.get("title", "").lower()
        slug = result.get("slug", "")

        # Se o título da busca bate parcialmente
        if title_lower in result_title or result_title in title_lower:
            if prefer_dubbed and "dublado" in slug:
                return slug
            elif not prefer_dubbed and "dublado" not in slug:
                return slug

    # Fallback: pega o primeiro resultado
    first_result = results[0]
    if prefer_dubbed:
        # Procura um com dublado
        for result in results:
            if "dublado" in result.get("slug", ""):
                return result.get("slug")
        return first_result.get("slug")
    else:
        return first_result.get("slug")
