import argparse
import random
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Jsonb

from app.db import pool
from app.graph import best_shortest_route, load_graph, load_points, person_distances

PAR_BY_WEEKDAY = [3, 3, 4, 4, 4, 5, 5]   # Monday to Sunday (UTC)

ap = argparse.ArgumentParser()
ap.add_argument("--days", type=int, default=30)
ap.add_argument("--min-par", type=int, default=3)
ap.add_argument("--start-pool", type=int, default=1500, help="this many most-famous actors can start a puzzle")
ap.add_argument("--target-pool", type=int, default=6000, help="this many most-famous actors can be the target")
ap.add_argument("--min-credits", type=int, default=3)
ap.add_argument("--tries", type=int, default=25, help="start actors to try per day")
ap.add_argument("--cooldown", type=int, default=60, help="don't reuse an actor within this many days")
args = ap.parse_args()


def top_people(conn, limit):
    rows = conn.execute(
        """SELECT p.id FROM person p
           JOIN (SELECT person_id, COUNT(*) AS n FROM credit GROUP BY person_id) c ON c.person_id = p.id
           WHERE c.n >= %s ORDER BY p.total_votes DESC LIMIT %s""",
        (args.min_credits, limit),
    ).fetchall()
    return [r[0] for r in rows]


def name(conn, person_id):
    return conn.execute("SELECT name FROM person WHERE id = %s", (person_id,)).fetchone()[0]


with pool.connection() as conn:
    movies_of, cast_of = load_graph(conn)
    points = load_points(conn)
    starts = top_people(conn, args.start_pool)
    targets = top_people(conn, args.target_pool)
    print(f"{len(starts)} possible start actors, {len(targets)} possible targets")

    last_date, number = conn.execute(
        "SELECT MAX(play_date), COALESCE(MAX(number), 0) FROM puzzle"
    ).fetchone()
    today = datetime.now(timezone.utc).date()
    day = max(today, last_date + timedelta(days=1)) if last_date else today

    recent = set()
    for s, e in conn.execute(
        "SELECT start_person_id, end_person_id FROM puzzle WHERE play_date >= %s",
        (day - timedelta(days=args.cooldown),),
    ):
        recent |= {s, e}

    for _ in range(args.days):
        want = PAR_BY_WEEKDAY[day.weekday()]
        best = None                      # (par, start, target): highest par up to `want`

        for _ in range(args.tries):
            a = random.choice(starts)
            if a in recent:
                continue
            dist = person_distances(movies_of, cast_of, a)      # one search from this actor
            by_par = {}
            for t in targets:
                d = dist.get(t)
                if d is not None and d >= args.min_par and t not in recent:
                    by_par.setdefault(d, []).append(t)
            for d in range(want, args.min_par - 1, -1):
                if by_par.get(d):
                    if best is None or d > best[0]:
                        best = (d, a, random.choice(by_par[d]))
                    break
            if best and best[0] == want:
                break

        if not best:
            print(f"Stopped at {day}: no pair found. Try a bigger --target-pool or --min-credits 2.")
            break

        par, a, b = best
        route = best_shortest_route(movies_of, cast_of, points, a, b)
        number += 1
        conn.execute(
            """INSERT INTO puzzle (number, play_date, start_person_id, end_person_id, par, example_route)
               VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (play_date) DO NOTHING""",
            (number, day, a, b, par, Jsonb(route)),
        )
        recent |= {a, b}
        note = "" if par == want else f"  (wanted {want})"
        print(f"#{number}  {day}  par {par}{note}  {name(conn, a)} -> {name(conn, b)}")
        day += timedelta(days=1)

pool.close()