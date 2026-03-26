"""
Content-origin filter utilities.

Centralises the "JP DNA" check used in:
  - app/services/tmdb.py  (search_tmdb)
  - app/routes/home.py    (_get_western_cartoons)
"""

import re

# Matches Hiragana (\\u3040-\\u30ff) and CJK ideographs (\\u4e00-\\u9fff)
JP_REGEX = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


def is_japanese_content(item: dict) -> bool:
    """
    Return True if `item` (a TMDB result dict) appears to be Japanese content.

    Checks:
      - original_language == 'ja'
      - 'JP' in origin_country list
      - Kanji/Kana characters in the original name/title
    """
    lang: str = item.get("original_language", "")
    countries: list = item.get("origin_country", [])
    name: str = item.get("original_name") or item.get("original_title", "")

    return lang == "ja" or "JP" in countries or bool(JP_REGEX.search(name))
