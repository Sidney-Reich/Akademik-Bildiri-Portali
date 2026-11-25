"""Backend API (FastAPI).

Run:   uvicorn backend.app.main:app --reload
Open:  http://127.0.0.1:8000/docs   (interactive list of all endpoints)

Each task adds its endpoints in its own file (routes_t1.py ... routes_t4.py)
and registers it below with app.include_router(...).
"""
from fastapi import FastAPI

from .db import get_conn

app = FastAPI(title="Academic Paper Review Portal")


@app.get("/health")
def health():
    """Checks that the API is running and can reach the database."""
    with get_conn() as conn:
        version = conn.execute("SELECT version()").fetchone()[0]
        tables = conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'core'"
        ).fetchone()[0]
    return {"status": "ok", "database": version, "core_tables": tables}


# app.include_router(routes_t1.router)   # Eyup:   accounts, submission
# app.include_router(routes_t2.router)   # Kadir:  conference, assignment
# app.include_router(routes_t3.router)   # Sidney: review
# app.include_router(routes_t4.router)   # Selim:  decision