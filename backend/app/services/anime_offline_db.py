import json
import re
from pathlib import Path
from functools import lru_cache

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "anime-index.json"


@lru_cache(maxsize=1)
def load_offline_db() -> dict:
    with open(DB_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {int(k): v for k, v in raw.items()}


def get_anime_by_mal_id(mal_id: int) -> dict | None:
    return load_offline_db().get(mal_id)


def get_search_terms(mal_id: int) -> list[str]:
    entry = get_anime_by_mal_id(mal_id)
    if not entry:
        return []

    all_terms = [entry["title"]] + entry.get("synonyms", [])

    latin_terms = []
    for term in all_terms:
        non_latin = sum(1 for c in term if ord(c) > 0x024F)
        if non_latin / max(len(term), 1) < 0.4:
            latin_terms.append(term)

    seen = set()
    unique_terms = []
    for t in latin_terms:
        key = t.lower().strip()
        if key not in seen:
            seen.add(key)
            unique_terms.append(t)

    return unique_terms


def get_anime_type(mal_id: int) -> str:
    entry = get_anime_by_mal_id(mal_id)
    return entry.get("type", "UNKNOWN") if entry else "UNKNOWN"


def is_related_to(mal_id_a: int, mal_id_b: int) -> bool:
    entry = get_anime_by_mal_id(mal_id_a)
    if not entry:
        return False
    related_urls = entry.get("relatedAnime", [])
    for url in related_urls:
        match = re.search(r"myanimelist\.net/anime/(\d+)", url)
        if match and int(match.group(1)) == mal_id_b:
            return True
    return False
