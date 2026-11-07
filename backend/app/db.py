import os
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

load_dotenv()

pool = ConnectionPool(os.environ["DATABASE_URL"], min_size=1, max_size=5, open=True)

def query(sql, params=()):
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()

def query_one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None
