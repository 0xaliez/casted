import unicodedata


def norm(text: str) -> str:
    """Lowercase and strip accents. Used for the *_search columns and for search input."""
    t = unicodedata.normalize("NFKD", text)
    return "".join(c for c in t if not unicodedata.combining(c)).lower().strip()
