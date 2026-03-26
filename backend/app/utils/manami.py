import os
import json
import httpx
from app.utils import slugify

DB_URL = "https://github.com/manami-project/anime-offline-database/releases/latest/download/anime-offline-database-minified.json"
CACHE_DIR = "data"
DB_FILE = os.path.join(CACHE_DIR, "anime-offline-database.json")

def ensure_db_downloaded():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    
    if not os.path.exists(DB_FILE):
        print(f"[Manami] Baixando banco de dados offline...")
        try:
            with httpx.Client(follow_redirects=True, timeout=60.0) as client:
                resp = client.get(DB_URL)
                if resp.status_code == 200:
                    with open(DB_FILE, "w", encoding="utf-8") as f:
                        f.write(resp.text)
                    print("[Manami] Banco de dados salvo com sucesso.")
                else:
                    print(f"[Manami ERRO] Falha no download: {resp.status_code}")
        except Exception as e:
            print(f"[Manami ERRO] Exceção no download: {e}")

def get_anime_synonyms(mal_id: int) -> list[str]:
    ensure_db_downloaded()
    
    if not mal_id:
        return []

    try:
        if not os.path.exists(DB_FILE):
            return []
            
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        for entry in data.get("data", []):
            sources = entry.get("sources", [])
            # Procura por MyAnimeList ID
            has_mal = False
            for s in sources:
                if "myanimelist.net/anime/" in s:
                    # Extrai o ID da URL .../anime/123/...
                    parts = s.split("/")
                    for p in parts:
                        if p.isdigit() and int(p) == mal_id:
                            has_mal = True
                            break
                if has_mal: break
            
            if has_mal:
                synonyms = entry.get("synonyms", [])
                title = entry.get("title")
                all_names = list(set([title] + synonyms))
                # Filtra apenas nomes úteis para busca
                return [n for n in all_names if n]
                
    except Exception as e:
        print(f"[Manami] Erro ao buscar sinônimos: {e}")
        
    return []
