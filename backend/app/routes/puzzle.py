from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.db import query_one
from app.helpers import person_card

router = APIRouter()

@router.get("/puzzle/today")
def puzzle_today():
    today = datetime.now(timezone.utc).date()
    p = query_one("SELECT * FROM puzzle WHERE play_date = %s", (today,))
    if not p:
        p = query_one("SELECT * FROM puzzle WHERE play_date <= %s ORDER BY play_date DESC LIMIT 1", (today,))
    if not p:
        raise HTTPException(404, "No puzzle yet. Run make_puzzle.py")
    return {
            "number": p["number"],
            "date": str(p["play_date"]),
            "start": person_card(p["start_person_id"]),
            "end": person_card(p["end_person_id"]),
    }

