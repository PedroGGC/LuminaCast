"""
Cloudflare Worker Proxy Service

Faz a ponte entre o backend e o Cloudflare Worker que scrapeia o AnimeFire.
"""

import httpx
import urllib.parse
import logging

logger = logging.getLogger("cloudflare_worker")

WORKER_URL = "https://luminacast-worker.pedroogabrielg.workers.dev"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

HLS_FALLBACK = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"


async def get_episode_url_from_worker(episode_url: str) -> str:
    """
    Chama o Cloudflare Worker para obter a URL do vídeo.

    Args:
        episode_url: URL do episódio no AnimeFire (ex: https://animefire.io/animes/naruto-dublado/1)

    Returns:
        URL direta do vídeo (.mp4 ou .m3u8), ou fallback em caso de erro.
    """
    try:
        encoded_url = urllib.parse.quote(episode_url, safe="")
        worker_url = f"{WORKER_URL}/watch?url={encoded_url}"

        logger.info(f"[Worker] Chamando watch: {worker_url[:100]}...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(worker_url, headers=HEADERS)

            logger.info(f"[Worker] Watch status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                logger.info(f"[Worker] Watch response: {data}")

                if data.get("success") and data.get("video_url"):
                    video_url = data["video_url"]
                    logger.info(f"[Worker] Video URL: {video_url[:80]}...")
                    return video_url
                else:
                    logger.warning(f"[Worker] Watch sem video_url: {data.get('error')}")
            else:
                logger.warning(
                    f"[Worker] Watch status {response.status_code}: {response.text[:200]}"
                )

    except Exception as e:
        logger.error(f"Erro ao chamar Cloudflare Worker: {e}")

    return HLS_FALLBACK


async def resolve_episode_url(
    title: str, episode: int, prefer_dubbed: bool = True
) -> str:
    """
    Rota única que resolve o anime e retorna a URL do episódio.
    Faz a busca + construção da URL do episódio no Worker.

    Args:
        title: Título do anime
        episode: Número do episódio
        prefer_dubbed: Preferir versão dublada

    Returns:
        URL direta do vídeo (.mp4 ou .m3u8), ou fallback em caso de erro.
    """
    try:
        encoded_title = urllib.parse.quote(title, safe="")
        worker_url = f"{WORKER_URL}/resolve?title={encoded_title}&episode={episode}&dub={'true' if prefer_dubbed else 'false'}"

        logger.info(f"[Worker] Chamando: {worker_url[:100]}...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(worker_url, headers=HEADERS)

            logger.info(f"[Worker] Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                if data.get("success") and data.get("episode_url"):
                    episode_url = data["episode_url"]
                    logger.info(f"[Worker] Resolve OK: {episode_url}")

                    # Agora chama /watch com a URL do episódio
                    video_url = await get_episode_url_from_worker(episode_url)
                    logger.info(
                        f"[Worker] Watch retornou: {video_url[:80] if video_url else 'None'}..."
                    )
                    return video_url
                else:
                    logger.warning(f"[Worker] Resolve falhou: {data.get('error')}")
                    logger.warning(f"[Worker] Response completo: {data}")
            else:
                logger.warning(
                    f"[Worker] Status {response.status_code} - Response: {response.text[:200]}"
                )

    except Exception as e:
        logger.error(f"Erro ao resolver episódio via Worker: {e}")

    return HLS_FALLBACK
