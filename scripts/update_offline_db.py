import httpx
import asyncio
from pathlib import Path

OFFLINE_DB_URL = (
    "https://raw.githubusercontent.com/manami-project/"
    "anime-offline-database/refs/tags/2026-12/"
    "anime-offline-database-minified.json"
)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "anime-offline-database.json"


async def download_offline_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"[OfflineDB] Baixando banco de dados...")
    async with httpx.AsyncClient() as client:
        response = await client.get(OFFLINE_DB_URL, timeout=60)
        response.raise_for_status()
        DB_PATH.write_bytes(response.content)
    print(
        f"[OfflineDB] Banco salvo em {DB_PATH} ({DB_PATH.stat().st_size / 1024 / 1024:.1f} MB)"
    )


if __name__ == "__main__":
    asyncio.run(download_offline_db())
