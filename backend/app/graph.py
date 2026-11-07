from collections import deque


def load_graph(conn):
    """Read every credit into two lookups: actor -> films, film -> actors."""
    movies_of, cast_of = {}, {}
    for movie_id, person_id in conn.execute("SELECT movie_id, person_id FROM credit"):
        movies_of.setdefault(person_id, []).append(movie_id)
        cast_of.setdefault(movie_id, []).append(person_id)
    return movies_of, cast_of


def shortest_route(movies_of, cast_of, start, end):
    """Breadth-first search. Returns [actor, film, actor, ..., actor] or None."""
    prev = {("p", start): None}
    queue = deque([("p", start)])
    while queue:
        node = queue.popleft()
        if node == ("p", end):
            break
        kind, id_ = node
        if kind == "p":
            neighbours = [("m", m) for m in movies_of.get(id_, [])]
        else:
            neighbours = [("p", p) for p in cast_of.get(id_, [])]
        for n in neighbours:
            if n not in prev:
                prev[n] = node
                queue.append(n)

    if ("p", end) not in prev:
        return None
    route, node = [], ("p", end)
    while node:
        route.append(node[1])
        node = prev[node]
    return route[::-1]
