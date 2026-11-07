import argparse
from datetime import date, datetime, timezone

from psycopg.types.json import Jsonb

from app.db import pool
from app.graph import load_graph, shortest_route
from app.textutil import norm


def find_person(conn, name):
    row = conn.execute(
        "SELECT id, name FROM person WHERE name_search = %s ORDER BY total_votes DESC LIMIT 1",
        (norm(name),),
    ).fetchone()
    if not row:
        raise SystemExit(f"No actor named {name!r} in the database")
    return row


ap = argparse.ArgumentParser()
ap.add_argument("--start", required=True)
ap.add_argument("--end", required=True)
ap.add_argument("--date", help="YYYY-MM-DD, defaults to today (UTC)")
args = ap.parse_args()

with pool.connection() as conn:
    start, end = find_person(conn, args.start), find_person(conn, args.end)
    movies_of, cast_of = load_graph(conn)
    route = shortest_route(movies_of, cast_of, start[0], end[0])
    if not route:
        raise SystemExit("No route between them in this dataset")

    par = (len(route) - 1) // 2          # number of films in the route
    play_date = date.fromisoformat(args.date) if args.date else datetime.now(timezone.utc).date()
    number = conn.execute("SELECT COALESCE(MAX(number), 0) + 1 FROM puzzle").fetchone()[0]

    conn.execute(
        """INSERT INTO puzzle (number, play_date, start_person_id, end_person_id, par, example_route)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (play_date) DO UPDATE SET
             start_person_id = EXCLUDED.start_person_id,
             end_person_id = EXCLUDED.end_person_id,
             par = EXCLUDED.par,
             example_route = EXCLUDED.example_route""",
        (number, play_date, start[0], end[0], par, Jsonb(route)),
    )

    print(f"Puzzle for {play_date}: {start[1]} -> {end[1]}, par {par}")
    for i, id_ in enumerate(route):
        table = "person" if i % 2 == 0 else "movie"
        col = "name" if i % 2 == 0 else "title"
        print("  ", conn.execute(f"SELECT {col} FROM {table} WHERE id = %s", (id_,)).fetchone()[0])
    if par < 3:
        print("Warning: par under 3 is probably too easy for a daily puzzle.")

pool.close()
