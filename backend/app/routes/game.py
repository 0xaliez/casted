from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import query, query_one
from app.helpers import get_puzzle, img, in_cast, person_card
from app.scoring import compute_score, film_points, share_text

router = APIRouter()

class MoveIn(BaseModel):
    puzzle_number: int
    route: list[int]
    pick_id: int

@router.post("/move")
def move(body: MoveIn):
    p = get_puzzle(body.puzzle_number)
    route = body.route
    if not route or route[0] != p["start_person_id"]:
        raise HTTPException(400, "Route must start with the start actor")

    actors, films = route[0::2], route[1::2]
    last = route[-1]

    if len(route) % 2 == 1:
        film = query_one(
            "SELECT id, title, release_year, poster_path, obscurity, tier FROM movie WHERE id = %s",
            (body.pick_id,),
        )
        if not film:
            return {"ok": False, "reason": "unknown", "strike": False}
        if body.pick_id in films:
            return {"ok": False, "reason": "repeat", "strike": False}
        if not in_cast(body.pick_id, last):
            return {"ok": False, "reason": "not_in_filmography", "strike": True}
        return {
            "ok": True,
            "kind": "film",
            "film": {
                "id": film["id"], "title": film["title"], "year": film["release_year"],
                "poster": img(film["poster_path"]), "tier": film["tier"],
                "points": film_points(film["obscurity"]),
            },
            "reached_target": False,
        }

    # route ends with a film, so the pick must be an actor in that film's top 15
    person = query_one("SELECT id FROM person WHERE id = %s", (body.pick_id,))
    if not person:
        return {"ok": False, "reason": "unknown", "strike": False}
    if body.pick_id in actors:
        return {"ok": False, "reason": "repeat", "strike": False}
    if not in_cast(last, body.pick_id):
        return {"ok": False, "reason": "not_in_cast", "strike": True}
    return {
        "ok": True,
        "kind": "actor",
        "person": person_card(body.pick_id),
        "reached_target": body.pick_id == p["end_person_id"],
    }


class CompleteIn(BaseModel):
    puzzle_number: int
    route: list[int]
    strikes: int = 0


@router.post("/complete")
def complete(body: CompleteIn):
    p = get_puzzle(body.puzzle_number)
    r = body.route
    if len(r) < 3 or len(r) % 2 == 0 or r[0] != p["start_person_id"] or r[-1] != p["end_person_id"]:
        raise HTTPException(400, "Route doesn't connect today's two actors")

    actors, films = r[0::2], r[1::2]
    if len(set(actors)) != len(actors) or len(set(films)) != len(films):
        raise HTTPException(400, "Route repeats an actor or film")

    # every film must contain the actor before it and the actor after it
    pairs = {
        (row["movie_id"], row["person_id"])
        for row in query(
            "SELECT movie_id, person_id FROM credit WHERE movie_id = ANY(%s) AND person_id = ANY(%s)",
            (films, actors),
        )
    }
    for i, film in enumerate(films):
        if (film, actors[i]) not in pairs or (film, actors[i + 1]) not in pairs:
            raise HTTPException(400, "Route has a link that isn't in the data")

    movies = {m["id"]: m for m in query(
        "SELECT id, obscurity, tier FROM movie WHERE id = ANY(%s)", (films,))}
    points = [film_points(movies[f]["obscurity"]) for f in films]
    tiers = [movies[f]["tier"] for f in films]
    strikes = max(0, min(body.strikes, 3))     # strikes are reported by the browser
    score = compute_score(points, p["par"], strikes)

    return {
        "score": score,
        "par": p["par"],
        "films": len(films),
        "points": points,
        "tiers": tiers,
        "strikes": strikes,
        "share": share_text(p["number"], p["par"], tiers, strikes, score),
    }


class CutIn(BaseModel):
    puzzle_number: int


@router.post("/cut")
def cut(body: CutIn):
    p = get_puzzle(body.puzzle_number)
    route = []
    for i, id_ in enumerate(p["example_route"]):
        if i % 2 == 0:
            r = query_one("SELECT name FROM person WHERE id = %s", (id_,))
            route.append({"type": "actor", "id": id_, "name": r["name"]})
        else:
            r = query_one("SELECT title, release_year FROM movie WHERE id = %s", (id_,))
            route.append({"type": "film", "id": id_, "title": r["title"], "year": r["release_year"]})
    return {"par": p["par"], "route": route}
