from pathlib import Path
from app.db import pool

with pool.connection() as conn:
    conn.execute(Path("..\sql\schema.sql").read_text())

print("Tables ready")
