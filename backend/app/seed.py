import sys
import os
import asyncio
import httpx
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine
from app.models import Base, Category, Media, AnimeMapping

# Lista VIP de títulos para auto-seed (título, MAL ID)
AUTO_SEED_ANIMES = [
    ("Frieren", 52991), 
    ("Bleach", 269),  
    ("One Piece", 21),  
    ("Gachiakuta", 59062),
    ("Sakamoto Days", 58939),
    ("Spy x Family", 50265),
    ("Jujutsu Kaisen", 40748),
    ("Demon Slayer", 38000),
    ("Naruto Shippuden", 1735),
    ("Attack on Titan", 16498),
    ("Hunter x Hunter", 11061),
    ("Death Note", 1535),
    ("Boku no Hero Academia", 31964),
    ("Fullmetal Alchemist: Brotherhood", 5114),
    ("One Punch Man", 30276),
    ("Chainsaw Man", 44511),
    ("Tokyo Ghoul", 22319),
    ("Black Clover", 34572),
    ("Sword Art Online", 11757),
    ("Haikyuu!!", 20583),
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
OFFLINE_DB_PATH = Path("data/anime-offline-database.json")
OFFLINE_DB_VERSION_FILE = Path("data/.offline-db-version")


def get_latest_release_tag() -> str | None:
    """Obtém a tag da última release do anime-offline-database."""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                "https://api.github.com/repos/manami-project/"
                "anime-offline-database/releases/latest"
            )
            if resp.status_code == 200:
                return resp.json().get("tag_name")
    except Exception as e:
        print(f"✗ Erro ao buscar última release: {e}")
    return None


def download_offline_db():
    """
    Baixa o banco offline do Manami Project se necessário.
    Verifica a última release no GitHub e re-baixa se houver versão mais nova.
    O scraper usa esse arquivo para obter títulos, sinônimos e tipo (TV/Movie/OVA)
    de cada anime a partir do MAL ID, sem depender de API externa.
    """
    OFFLINE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    current_version = None
    if OFFLINE_DB_VERSION_FILE.exists():
        current_version = OFFLINE_DB_VERSION_FILE.read_text().strip()

    latest_version = get_latest_release_tag()
    if not latest_version:
        latest_version = current_version or "2026-12"

    if OFFLINE_DB_PATH.exists() and current_version == latest_version:
        size_mb = OFFLINE_DB_PATH.stat().st_size / 1024 / 1024
        print(f"✓ Banco offline atualizado ({latest_version}, {size_mb:.1f} MB)")
        return

    print(f"↓ Baixando anime-offline-database {latest_version} (~60 MB)...")

    url = (
        f"https://github.com/manami-project/anime-offline-database/"
        f"releases/download/{latest_version}/anime-offline-database-minified.json"
    )
    try:
        with httpx.stream("GET", url, timeout=120, follow_redirects=True) as r:
            r.raise_for_status()
            with open(OFFLINE_DB_PATH, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=8192):
                    f.write(chunk)
        OFFLINE_DB_VERSION_FILE.write_text(latest_version)
        size_mb = OFFLINE_DB_PATH.stat().st_size / 1024 / 1024
        print(f"✓ Banco offline salvo ({latest_version}, {size_mb:.1f} MB)")
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
                    f"  [OK] Mapping: MAL {m_data['mal_id']} → {m_data['animefire_slug']}"
                )

        db.commit()
        print("[OK] Seed concluído.")

    except Exception as e:
        db.rollback()
        print(f"[ERRO] Erro no seed: {e}")
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
        for title, mal_id in AUTO_SEED_ANIMES:
            print(f"  → Sync: {title} (MAL {mal_id})")
            try:
                await sync_anime_by_mal_id(mal_id, db)
            except Exception as e:
                print(f"  ✗ Erro no sync de {title}: {e}")
            await asyncio.sleep(2)  # Rate limit protection

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
