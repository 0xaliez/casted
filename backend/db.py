import os
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool

load_dotenv()

pool = ConnectionPool(os.environ["DATABASE_URL"], min_size=1, max_size=5, open=True)
