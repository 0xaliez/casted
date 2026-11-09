import argparse
import random
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Jsonb

from app.db import pool
from app.graph import load_graph, load_points, best_shortest_route, shortest_route

ap = argparse.ArgumentParser()
ap.add_argument("--days", type=int, default=30)
ap.add_argument("--min-par", type=int, default=3)
ap.add_argument("--max-par", type=int, default=5)
ap.add_argument("--cooldown", type=int, default=60, help="don't reuse an actor within this many days")
args = ap.parse_args()


def name(conn, person_id):
    return conn.execute("SELECT name FROM person WHERE id = %s", (person_id,)).fetchone()[0]


with pool.connection() as conn:
    movies_of, cast_of = load_graph(conn)
    points = load_points(conn)
    candidates = [r[0] for r in conn.execute("SELECT id FROM person WHERE endpoint_eligible")]
    if len(candidates) < 20:
        raise SystemExit("Too few endpoint_eligible actors. Re-run the ingest so it finishes its last step.")

    last_date, number = conn.execute(
        "SELECT MAX(play_date), COALESCE(MAX(number), 0) FROM puzzle"
    ).fetchone()
    today = datetime.now(timezone.utc).date()
    day = max(today, last_date + timedelta(days=1)) if last_date else today

    # actors used recently are skipped, so the same faces don't keep coming back
    recent = set()
    for s, e in conn.execute(
        "SELECT start_person_id, end_person_id FROM puzzle WHERE play_date >= %s",
        (day - timedelta(days=args.cooldown),),
    ):
        recent |= {s, e}

    for _ in range(args.days):
        route = None
        for _ in range(300):
            a, b = random.sample(candidates, 2)
            if a in recent or b in recent:
                continue
            # cheap check first: is the shortest route the right length?
            r = shortest_route(movies_of, cast_of, a, b)
            if r and args.min_par <= (len(r) - 1) // 2 <= args.max_par:
                # same length, but pick the shortest route with the deepest films
                route = best_shortest_route(movies_of, cast_of, points, a, b) or r
                break
        if not route:
            print(f"Stopped at {day}: no suitable pair found. Widen --min-par/--max-par.")
            break

        number += 1
        par = (len(route) - 1) // 2
        conn.execute(
            """INSERT INTO puzzle (number, play_date, start_person_id, end_person_id, par, example_route)
               VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (play_date) DO NOTHING""",
            (number, day, route[0], route[-1], par, Jsonb(route)),
        )
        recent |= {route[0], route[-1]}
        print(f"#{number}  {day}  par {par}  {name(conn, route[0])} -> {name(conn, route[-1])}")
        day += timedelta(days=1)

pool.close()