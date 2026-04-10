import json
import re
from pathlib import Path

DB_PATH = Path("backend/data/anime-offline-database.jsonl")
OUT_PATH = Path("backend/data/anime-index.json")

print("Lendo arquivo JSONL (58MB)...")

# O arquivo tem um header na primeira linha, então precisamos pular
with open(DB_PATH, "r", encoding="utf-8") as f:
    # Primeira linha é o header do schema
    header = json.loads(f.readline())
    print(f"Schema: {header.get('$schema', 'unknown')}")
    print(f"Last Update: {header.get('lastUpdate', 'unknown')}")

    # Agora processa o resto
    index = {}
    count = 0

    for line in f:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except:
            continue

        mal_id = None
        for source_url in entry.get("sources", []):
            m = re.search(r"myanimelist\.net/anime/(\d+)", source_url)
            if m:
                mal_id = int(m.group(1))
                break
        if not mal_id:
            continue

        index[mal_id] = {
            "title": entry.get("title", ""),
            "synonyms": entry.get("synonyms", []),
            "type": entry.get("type", "UNKNOWN"),
        }
        count += 1

        if count % 1000 == 0:
            print(f"  Processados: {count} animes...")

print(f"Indexados {count} animes.")
print(f"Salvando arquivo reduzido...")
with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False)

print(f"✅ {len(index)} animes indexados!")
print(f"Arquivo salvo em: {OUT_PATH}")
