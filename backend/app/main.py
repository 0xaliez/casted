from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import query
from app.routes import game, puzzle, search

app = FastAPI(title="Casted API")
app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
)

app.include_router(puzzle.router)
app.include_router(search.router)
app.include_router(game.router)


@app.get("/health")
def health():
    query("SELECT 1")
    return {"ok": True}
