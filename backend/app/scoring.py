STRIKE_PENALTY = 5
TIER_SQUARE = {1: "⬜", 2: "🟦", 3: "🟨"}


def film_points(obscurity: float) -> int:
    return round(100 * obscurity)


def compute_score(points: list[int], par: int, strikes: int) -> int:
    films = len(points)
    mean_points = sum(points) / films
    efficiency = min(1, par / films)      # a route shorter than par gets no bonus
    raw = round(mean_points * efficiency)
    return max(0, raw - STRIKE_PENALTY * strikes)


def share_text(number: int, par: int, tiers: list[int], strikes: int, score: int) -> str:
    grid = "".join(TIER_SQUARE[t] for t in tiers)
    if strikes:
        grid += " " + "🟥" * strikes
    return f"Casted #{number}  par {par}\n{grid}\n{score}/100"
