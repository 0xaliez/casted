import argparse
import asyncio
import os
import re
import httpx
from dotenv import load_dotenv

from app.db import pool
from app.textutil import norm

load_dotenv()
TOKEN = os.environ["TMDB_API_KEY"]
BASE = "https://api.themoviedb.org/3"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "accept": "application/json"}

CAST_CAP = 15            # only the first 15 billed count
MIN_RUNTIME = 40         # minutes
MIN_VOTES = 20
BANNED_GENRES = {99, 10770}   # documentary, TV movie
SELF_RE = re.compile(r"\b(self|himself|herself|themselves)\b", re.I)


async def get(client, sem, path, params=None):
    """GET with a concurrency limit and retries on rate limits and server errors."""
    async with sem:
        for attempt in range(5):
            try:
                r = await client.get(f"{BASE}{path}", params=params)
            except httpx.TransportError:
                await asyncio.sleep(2 ** attempt)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                await asyncio.sleep(float(r.headers.get("Retry-After", 2 ** attempt)))
                continue
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
    return None


async def discover_ids(client, sem, year, pages):
    """Most-voted films released in one year (20 per page)."""
    ids = []
    for page in range(1, pages + 1):
        data = await get(client, sem, "/discover/movie", {
            "sort_by": "vote_count.desc",
            "include_adult": "false",
            "vote_count.gte": MIN_VOTES,
            "with_runtime.gte": MIN_RUNTIME,
            "primary_release_year": year,
            "page": page,
        })
        if not data or not data["results"]:
            break
        ids += [m["id"] for m in data["results"]]
        if page >= data["total_pages"]:
            break
    return ids


def clean(d):
    """Apply the filters. Returns a tidy dict, or None if the film is rejected."""
    if d.get("status") != "Released" or d.get("adult"):
        return None
    if not d.get("release_date") or (d.get("runtime") or 0) < MIN_RUNTIME:
        return None
    if (d.get("vote_count") or 0) < MIN_VOTES:
        return None
    genres = [g["id"] for g in d.get("genres", [])]
    if BANNED_GENRES & set(genres):
        return None

    cast = [
        c for c in d["credits"]["cast"]
        if c.get("known_for_department") == "Acting"
        and c["order"] < CAST_CAP
        and not SELF_RE.search(c.get("character") or "")
    ]
    if len(cast) < 2:
        return None

    return {
        "id": d["id"],
        "title": d["title"],
        "year": int(d["release_date"][:4]),
        "runtime": d["runtime"],
        "genres": genres,
        "poster": d.get("poster_path"),
        "votes": d["vote_count"],
        "cast": cast,
    }


async def fetch_movie(client, sem, movie_id):
    d = await get(client, sem, f"/movie/{movie_id}", {"append_to_response": "credits"})
    return clean(d) if d else None


def save(conn, m):
    # obscurity and tier are placeholders here; finalize() computes the real values
    conn.execute(
        """INSERT INTO movie (id, title, title_search, release_year, runtime,
                              genres, poster_path, vote_count, obscurity, tier)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, 3)
           ON CONFLICT (id) DO NOTHING""",
        (m["id"], m["title"], norm(m["title"]), m["year"], m["runtime"],
         m["genres"], m["poster"], m["votes"]),
    )
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO person (id, name, name_search, profile_path)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (id) DO UPDATE
               SET profile_path = COALESCE(person.profile_path, EXCLUDED.profile_path)""",
            [(c["id"], c["name"], norm(c["name"]), c.get("profile_path")) for c in m["cast"]],
        )
        cur.executemany(
            """INSERT INTO credit (movie_id, person_id, billing_order)
               VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
            [(m["id"], c["id"], c["order"]) for c in m["cast"]],
        )


def finalize(endpoint_count=500, min_credits=5):
    """Compute obscurity, tiers, person vote totals and puzzle-eligible actors."""
    with pool.connection() as conn:
        conn.execute("""
            WITH r AS (SELECT id, percent_rank() OVER (ORDER BY vote_count) AS pr FROM movie)
            UPDATE movie m
            SET obscurity = 1 - r.pr,
                tier = CASE WHEN 1 - r.pr < 0.25 THEN 1
                            WHEN 1 - r.pr < 0.60 THEN 2 ELSE 3 END
            FROM r WHERE r.id = m.id""")
        conn.execute("""
            UPDATE person p SET total_votes = s.v
            FROM (SELECT c.person_id, SUM(m.vote_count) AS v
                  FROM credit c JOIN movie m ON m.id = c.movie_id
                  GROUP BY c.person_id) s
            WHERE s.person_id = p.id""")
        conn.execute("UPDATE person SET endpoint_eligible = FALSE")
        conn.execute("""
            UPDATE person SET endpoint_eligible = TRUE WHERE id IN (
                SELECT p.id FROM person p
                JOIN (SELECT person_id, COUNT(*) AS n FROM credit GROUP BY person_id) c
                  ON c.person_id = p.id
                WHERE c.n >= %s
                ORDER BY p.total_votes DESC LIMIT %s)""", (min_credits, endpoint_count))


async def main(start_year, end_year, pages):
    sem = asyncio.Semaphore(10)
    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        print("Collecting film ids...")
        lists = await asyncio.gather(
            *(discover_ids(client, sem, y, pages) for y in range(start_year, end_year + 1))
        )
        ids = sorted({i for lst in lists for i in lst})

        with pool.connection() as conn:
            have = {row[0] for row in conn.execute("SELECT id FROM movie").fetchall()}
        todo = [i for i in ids if i not in have]
        print(f"{len(ids)} found, {len(todo)} new")

        saved = skipped = 0
        for i in range(0, len(todo), 100):
            movies = await asyncio.gather(
                *(fetch_movie(client, sem, mid) for mid in todo[i:i + 100])
            )
            with pool.connection() as conn:
                for m in movies:
                    if m:
                        save(conn, m)
                        saved += 1
                    else:
                        skipped += 1
            print(f"  {i + len(movies)}/{len(todo)}  saved {saved}, filtered out {skipped}")

    finalize()
    print("Done.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-year", type=int, default=1970)
    ap.add_argument("--end-year", type=int, default=2025)
    ap.add_argument("--pages", type=int, default=5, help="20 films per page, per year")
    args = ap.parse_args()
    asyncio.run(main(args.start_year, args.end_year, args.pages))
    pool.close()
