from fastapi import FastAPI
from db import pool

app = FastAPI(title="Casted API")

@app.get("/health")
def health():
    with pool.connection() as conn:        
        conn.execute("SELECT 1")
    return {"ok": True}
