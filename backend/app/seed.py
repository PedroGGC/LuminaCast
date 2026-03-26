import sys
import os
import asyncio
import httpx
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine
from app.models import Base, Category, Media, AnimeMapping

# Lista VIP de títulos para auto-seed
AUTO_SEED_ANIMES = [
    "Frieren",
    "Bleach",
    "One Piece",
    "Gachiakuta",
    "Sakamoto Days",
    "Spy x Family",
    "Jujutsu Kaisen",
    "Demon Slayer",
    "Naruto Shippuden",
    "Attack on Titan",
    "Hunter x Hunter",
    "Death Note",
    "Boku no Hero Academia",
    "Fullmetal Alchemist: Brotherhood",
    "One Punch Man",
    "Chainsaw Man",
    "Tokyo Ghoul",
    "Black Clover",
    "Sword Art Online",
    "Haikyuu!!",
]

AUTO_SEED_DRAWINGS = [
    "Hora de Aventura",
    "Apenas um Show",
    "Steven Universo",
    "Ben 10",
    "Gravity Falls",
    "O Incrível Mundo de Gumball",
    "Jovens Titãs em Ação",
    "Avatar: A Lenda de Aang",
    "Rick and Morty",
    "Bob Esponja",
    "Os Simpsons",
    "Futurama",
    "Phineas e Ferb",
    "As Meninas Superpoderosas",
    "O Laboratório de Dexter",
    "Coragem o Cão Covarde",
    "Mutante Rex",
    "Kim Possible",
    "Invasor Zim",
    "Danny Phantom",
]

# ─────────────────────────────────────────────
# Banco offline do Manami Project
# Usado pelo scraper para resolver slugs automaticamente.
# Os mapeamentos manuais abaixo têm PRIORIDADE sobre o scoring automático.
# ─────────────────────────────────────────────
OFFLINE_DB_URL = (
    "https://raw.githubusercontent.com/manami-project/"
    "anime-offline-database/refs/tags/2026-12/"
    "anime-offline-database-minified.json"
)
OFFLINE_DB_PATH = Path("data/anime-offline-database.json")


def download_offline_db():
    """
    Baixa o banco offline do Manami Project se ainda não existir.
    O scraper usa esse arquivo para obter títulos, sinônimos e tipo (TV/Movie/OVA)
    de cada anime a partir do MAL ID, sem depender de API externa.
    """
    OFFLINE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if OFFLINE_DB_PATH.exists():
        size_mb = OFFLINE_DB_PATH.stat().st_size / 1024 / 1024
        print(f"✓ Banco offline já existe ({size_mb:.1f} MB) — pulando download.")
        return

    print(f"↓ Baixando anime-offline-database (~30 MB)...")
    try:
        with httpx.stream(
            "GET", OFFLINE_DB_URL, timeout=120, follow_redirects=True
        ) as r:
            r.raise_for_status()
            with open(OFFLINE_DB_PATH, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=8192):
                    f.write(chunk)
        size_mb = OFFLINE_DB_PATH.stat().st_size / 1024 / 1024
        print(f"✓ Banco offline salvo em {OFFLINE_DB_PATH} ({size_mb:.1f} MB)")
    except Exception as e:
        print(f"✗ Falha ao baixar banco offline: {e}")
        print("  O scraper vai operar sem o banco offline até o próximo seed.")


def seed_database():
    db = SessionLocal()
    try:
        # Base.metadata.drop_all(bind=engine) # Removido para não zerar o banco
        Base.metadata.create_all(bind=engine)

        # ── Categorias ────────────────────────────────────────────
        cat_anime = db.query(Category).filter_by(name="Animes").first()
        if not cat_anime:
            cat_anime = Category(name="Animes", slug="animes")
            db.add(cat_anime)
            db.commit()
            db.refresh(cat_anime)

        # ── Mapeamentos manuais (overrides) ───────────────────────
        #
        # QUANDO adicionar aqui:
        #   - Animes cujo slug no AnimeFire é muito diferente do título em romaji
        #   - Animes onde o scoring automático escolhe slug errado nos testes
        #   - Animes com sufixos incomuns no AnimeFire (ex: -tv, -2024, numerais)
        #
        # QUANDO NÃO adicionar:
        #   - Animes populares com slug óbvio (ex: "one-piece") — o scoring resolve
        #   - Sequências/temporadas já reconhecidas pelo MAL ID separado
        #
        # O scraper consulta esta tabela ANTES de rodar o scoring automático.
        # Se encontrar um registro aqui, usa o slug fixo e não chama o AnimeFire.
        #
        # Formato do animefire_slug: apenas o slug, SEM domínio e SEM sufixo.
        # O scraper monta a URL completa:
        #   https://animefire.io/animes/{slug}-todos-os-episodios
        #
        mappings = []

        for m_data in mappings:
            existing = db.query(AnimeMapping).filter_by(mal_id=m_data["mal_id"]).first()
            if not existing:
                mapping = AnimeMapping(**m_data)
                db.add(mapping)
                print(
                    f"  ✓ Mapping: MAL {m_data['mal_id']} → {m_data['animefire_slug']}"
                )

        db.commit()
        print("✓ Seed concluído.")

    except Exception as e:
        db.rollback()
        print(f"✗ Erro no seed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    # 1. Banco offline (necessário para o scraper funcionar automaticamente)
    download_offline_db()

    # 2. Banco relacional (categorias + mapeamentos manuais)
    seed_database()


# ─────────────────────────────────────────────
# Auto-Seed: População automática no startup
# ─────────────────────────────────────────────
async def auto_seed_database():
    """
    Executa seed automático se o banco estiver vazio.
    Popula com uma lista VIP de animes e desenhos populares.
    """
    db = SessionLocal()
    try:
        # Verifica se já tem mídias no banco
        media_count = db.query(Media).count()
        if media_count > 0:
            print(f"[Auto-Seed] Banco já populado ({media_count} mídias). Abortando.")
            return

        print("[Auto-Seed] Iniciando population...")

        # Mapeia títulos para MAL ID via busca no Jikan
        async def get_mal_id(title: str) -> int | None:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        "https://api.jikan.moe/v4/anime",
                        params={"q": title, "limit": 1},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        items = data.get("data", [])
                        if items:
                            return items[0].get("mal_id")
            except Exception as e:
                print(f"[Auto-Seed] Erro ao buscar MAL ID para '{title}': {e}")
            return None

        # Mapeia títulos para TMDB ID via busca no TMDB
        async def get_tmdb_id(title: str) -> int | None:
            import os

            tmdb_key = os.getenv("TMDB_API_KEY")
            if not tmdb_key:
                return None
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        "https://api.themoviedb.org/3/search/tv",
                        params={
                            "api_key": tmdb_key,
                            "query": title,
                            "language": "pt-BR",
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        results = data.get("results", [])
                        if results:
                            return results[0].get("id")
            except Exception as e:
                print(f"[Auto-Seed] Erro ao buscar TMDB ID para '{title}': {e}")
            return None

        # Importa o sync_service
        from app.services.sync_service import sync_anime_by_mal_id, sync_media_by_id

        # ── Seed Animes ─────────────────────────────
        print("[Auto-Seed] Populando Animes...")
        for title in AUTO_SEED_ANIMES:
            mal_id = await get_mal_id(title)
            if mal_id:
                print(f"  → Sync: {title} (MAL {mal_id})")
                try:
                    await sync_anime_by_mal_id(mal_id, db)
                except Exception as e:
                    print(f"  ✗ Erro no sync de {title}: {e}")
                await asyncio.sleep(2)  # Rate limit protection
            else:
                print(f"  ✗ MAL ID não encontrado para: {title}")

        # ── Seed Desenhos ────────────────────────────
        print("[Auto-Seed] Populando Desenhos...")
        for title in AUTO_SEED_DRAWINGS:
            tmdb_id = await get_tmdb_id(title)
            if tmdb_id:
                print(f"  → Sync: {title} (TMDB {tmdb_id})")
                try:
                    await sync_media_by_id(str(tmdb_id), "desenho", db)
                except Exception as e:
                    print(f"  ✗ Erro no sync de {title}: {e}")
                await asyncio.sleep(2)  # Rate limit protection
            else:
                print(f"  ✗ TMDB ID não encontrado para: {title}")

        print("[Auto-Seed] Concluído!")

    except Exception as e:
        print(f"[Auto-Seed] Erro geral: {e}")
    finally:
        db.close()
