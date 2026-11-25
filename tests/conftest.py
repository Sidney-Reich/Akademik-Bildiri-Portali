"""Shared test setup.

Every test gets `conn`: a connection inside one transaction that is rolled
back at the end, so tests never leave data behind and never affect each other.
"""
import os
import pathlib

import psycopg
import pytest
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
URL = (
    f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.environ.get('POSTGRES_HOST', 'localhost')}:{os.environ.get('POSTGRES_PORT', '5432')}"
    f"/{os.environ['POSTGRES_DB']}"
)


@pytest.fixture
def conn():
    with psycopg.connect(URL) as c:
        yield c
        c.rollback()  # undo everything the test did