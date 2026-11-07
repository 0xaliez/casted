from fastapi import APIRouter, Query

from app.db import query
from app.helpers import img
from app.textutil import norm

router = APIRouter()

def search_text(q):
    return norm(q).replace("%", "").replace("_","")

@router.get("/search/movies")
def search_movies(q: str = Query(..., min_length=2, max_length=80)):
    n = search_text(q)
    if len(n) < 2:
        return []
    rows = query(
        """SELECT m.id, m.title, m.release_year, m.poster_path,
                  (SELECT array_agg(t.name ORDER BY t.billing_order) FROM (
                       SELECT p.name, c.billing_order
                       FROM credit c JOIN person p ON p.id = c.person_id
                       WHERE c.movie_id = m.id ORDER BY c.billing_order LIMIT 2) t) AS top_billed
           FROM movie m
           WHERE m.title_search LIKE %s OR m.title_search %% %s
           ORDER BY (m.title_search LIKE %s) DESC, similarity(m.title_search, %s) DESC, m.vote_count DESC
           LIMIT 8""",
        (f"%{n}%", n, f"{n}%", n),
    )
    return [
        {"id": r["id"], "title": r["title"], "year": r["release_year"],
         "poster": img(r["poster_path"]), "top_billed": r["top_billed"] or []}
        for r in rows
    ]

@router.get("/search/people")
def search_people(q: str = Query(..., min_length=2, max_length=80)):
    n = search_text(q)
    if len(n) < 2:
        return []
    rows = query(
        """SELECT p.id, p.name, p.profile_path,
                  (SELECT m.title FROM credit c JOIN movie m ON m.id = c.movie_id
                   WHERE c.person_id = p.id ORDER BY m.vote_count DESC LIMIT 1) AS known_for
           FROM person p
           WHERE p.name_search LIKE %s OR p.name_search %% %s
           ORDER BY (p.name_search LIKE %s) DESC, similarity(p.name_search, %s) DESC, p.total_votes DESC
           LIMIT 8""",
        (f"%{n}%", n, f"{n}%", n),
    )
    return [
        {"id": r["id"], "name": r["name"], "photo": img(r["profile_path"]), "known_for": r["known_for"]}
        for r in rows
    ]
