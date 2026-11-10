import argparse
import random
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Jsonb

from app.db import pool
from app.graph import best_shortest_route, load_graph, load_points, person_distances

ap = argparse.ArgumentParser()
ap.add_argument("--days", type=int, default=30)
ap.add_argument("--pars", default="3,4,5",
                help="pars to pick from at random; repeat one to make it likelier, e.g. 3,3,4,5")
ap.add_argument("--min-par", type=int, default=3)
ap.add_argument("--start-pool", type=int, default=800, help="this many top actors can start a puzzle")
ap.add_argument("--target-pool", type=int, default=2500, help="this many top actors can be the target")
ap.add_argument("--min-credits", type=int, default=3,
                help="lead credits needed in qualifying films (see --lead, --endpoint-since)")
ap.add_argument("--lead", type=int, default=5,
                help="only the first N billed count as a lead credit")
ap.add_argument("--endpoint-since", type=int, default=1995,
                help="only films released this year or later count towards an actor's fame")
ap.add_argument("--endpoint-lang", default="en",
                help="original language(s) of films that count, comma separated, e.g. en,fr. "
                     "'any' switches the filter off. Films in the middle of a route can be any language.")
ap.add_argument("--tries", type=int, default=25, help="start actors to try per day")
ap.add_argument("--cooldown", type=int, default=60, help="don't reuse an actor within this many days")
ap.add_argument("--show-pool", action="store_true",
                help="print sample names from the start and target pools, then exit")
args = ap.parse_args()

PARS = [int(x) for x in args.pars.split(",")]
LANGS = None if args.endpoint_lang == "any" else args.endpoint_lang.split(",")


def top_people(conn, limit):
    """Actors ranked by votes of the films they led (top --lead billed) since --endpoint-since."""
    conds = ["c.billing_order < %s", "m.release_year >= %s", "p.profile_path IS NOT NULL"]
    params = [args.lead, args.endpoint_since]
    if LANGS is not None:
        conds.append("m.original_language = ANY(%s)")
        params.append(LANGS)
    params += [args.min_credits, limit]
    rows = conn.execute(
        f"""SELECT p.id FROM person p
            JOIN credit c ON c.person_id = p.id
            JOIN movie m ON m.id = c.movie_id
            WHERE {' AND '.join(conds)}
            GROUP BY p.id
            HAVING COUNT(*) >= %s
            ORDER BY SUM(m.vote_count) DESC
            LIMIT %s""",
        params,
    ).fetchall()
    return [r[0] for r in rows]


def names(conn, ids):
    found = dict(conn.execute("SELECT id, name FROM person WHERE id = ANY(%s)", (ids,)).fetchall())
    return ", ".join(found[i] for i in ids)


def name(conn, person_id):
    return conn.execute("SELECT name FROM person WHERE id = %s", (person_id,)).fetchone()[0]


with pool.connection() as conn:
    starts = top_people(conn, args.start_pool)
    targets = top_people(conn, args.target_pool)
    print(f"{len(starts)} possible start actors, {len(targets)} possible targets")

    if args.show_pool:
        for label, pool_ids in (("START POOL", starts), ("TARGET POOL", targets)):
            n = len(pool_ids)
            print(f"\n{label}")
            for where, i in (("top", 0), ("middle", n // 2), ("bottom", max(0, n - 12))):
                print(f"  {where}: {names(conn, pool_ids[i:i + 12])}")
        raise SystemExit

    movies_of, cast_of = load_graph(conn)      # the whole graph: every language and era
    points = load_points(conn)

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
        want = random.choice(PARS)
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