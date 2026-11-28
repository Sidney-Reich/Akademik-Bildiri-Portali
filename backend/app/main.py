"""Backend API (FastAPI).

Run:   uvicorn backend.app.main:app --reload
Open:  http://127.0.0.1:8000/docs   (interactive list of all endpoints)

Each task adds its endpoints in its own file (routes_t1.py ... routes_t4.py)
and registers it below with app.include_router(...).
"""
import pathlib
import time

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from . import routes_t1
from .db import get_conn

app = FastAPI(title="Academic Paper Review Portal")


@app.middleware("http")
async def note_arrival(request: Request, call_next):
    """When the request reached the server, before its body is read (BR-04)."""
    request.state.arrived = time.monotonic()
    return await call_next(request)


@app.get("/health")
def health():
    """Checks that the API is running and can reach the database."""
    with get_conn() as conn:
        version = conn.execute("SELECT version()").fetchone()[0]
        tables = conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'core'"
        ).fetchone()[0]
    return {"status": "ok", "database": version, "core_tables": tables}


app.include_router(routes_t1.router)     # Eyup:   accounts, submission
# app.include_router(routes_t2.router)   # Kadir:  conference, assignment
# app.include_router(routes_t3.router)   # Sidney: review
# app.include_router(routes_t4.router)   # Selim:  decision

# screens (plain HTML): http://127.0.0.1:8000/ui/
FRONTEND = pathlib.Path(__file__).resolve().parents[2] / "frontend"
app.mount("/ui", StaticFiles(directory=FRONTEND, html=True), name="ui")
