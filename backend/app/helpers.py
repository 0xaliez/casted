from fastapi import HTTPException

from app.db import query_one

TMDB_IMG = "https://image.tmdb.org/t/p"

def img(path, size="w185"):
    return f"{TMDB_IMG}/{size}/{path}" if path else None

def get_puzzle(number):
    p = query_one("SELECT * FROM puzzle WHERE number = %s", (number,))
    if not p:
        raise HTTPException(404, "Unknown puzzle")
    return p

def person_card(person_id):
    r = query_one("SELECT id, name, profile_path FROM person WHERE id = %s", (person_id,))
    return {"id": r["id"], "name": r["name"], "photo": img(r["profile_path"])}

def in_cast(movie_id, person_id):
    return query_one(
            "SELECT 1 AS x FROM credit WHERE movie_id = %s AND person_id = %s", (movie_id, person_id)) is not None
