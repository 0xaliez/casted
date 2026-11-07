from pathlib import Path
from db import pool

with pool.connection() as conn:
    conn.execute(Path("schema.sql").read_text())

print("Tables ready")
