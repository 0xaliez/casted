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

def load_points(conn):
    """Film id -> points (100 * obscurity)."""
    return {mid: round(100 * ob) for mid, ob in conn.execute("SELECT id, obscurity FROM movie")}


def best_shortest_route(movies_of, cast_of, points, start, end):
    """Among all shortest routes, the one with the highest total film points."""
    dist = {("p", start): 0}
    best = {("p", start): (0, None)}      # node -> (points so far, previous node)
    queue = deque([("p", start)])
    while queue:
        node = queue.popleft()
        if node == ("p", end):
            break
        kind, id_ = node
        if kind == "p":
            nbrs = [("m", m) for m in movies_of.get(id_, [])]
        else:
            nbrs = [("p", p) for p in cast_of.get(id_, [])]
        for n in nbrs:
            if n not in dist:
                dist[n] = dist[node] + 1
                queue.append(n)
            if dist[n] == dist[node] + 1:           # only follow shortest-route edges
                total = best[node][0] + (points.get(n[1], 0) if n[0] == "m" else 0)
                if n not in best or total > best[n][0]:
                    best[n] = (total, node)

    if ("p", end) not in best:
        return None
    route, node = [], ("p", end)
    while node:
        route.append(node[1])
        node = best[node][1]
    return route[::-1]

def person_distances(movies_of, cast_of, start):
    """Films away from `start` for every actor reachable from them: {actor_id: films}."""
    depth = {("p", start): 0}
    queue = deque([("p", start)])
    result = {start: 0}
    while queue:
        node = queue.popleft()
        kind, id_ = node
        if kind == "p":
            nbrs = [("m", m) for m in movies_of.get(id_, [])]
        else:
            nbrs = [("p", p) for p in cast_of.get(id_, [])]
        for n in nbrs:
            if n not in depth:
                depth[n] = depth[node] + 1
                queue.append(n)
                if n[0] == "p":
                    result[n[1]] = depth[n] // 2
    return result