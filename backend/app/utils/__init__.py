import re
import unicodedata

def slugify(value: str) -> str:
    """
    Converte uma string em um slug válido para URLs (AnimeFire).
    Remove acentos, caracteres especiais e substitui espaços por hífens.
    """
    value = str(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)
