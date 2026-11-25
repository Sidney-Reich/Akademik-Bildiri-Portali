"""Database connection for the backend (settings come from .env)."""
import os
import pathlib

import psycopg
from dotenv import load_dotenv

load_dotenv(pathlib.Path(__file__).resolve().parents[2] / ".env")

URL = (
    f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.environ.get('POSTGRES_HOST', 'localhost')}:{os.environ.get('POSTGRES_PORT', '5432')}"
    f"/{os.environ['POSTGRES_DB']}"
)


def get_conn():
    """One connection per request. Use it with `with get_conn() as conn:`;
    it commits at the end of the block, or rolls back if an error happens."""
    return psycopg.connect(URL)