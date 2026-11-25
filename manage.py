"""Project commands. Usage: python manage.py <command>

  up        start the database (Docker)
  down      stop the database (data is kept)
  migrate   apply new files from db/migrations, in name order
  seed      load db/seed/seed_minimal.sql
  reset     delete everything, then migrate and seed
  status    list applied and pending migration files
  test      run all tests        e.g. python manage.py test
            run one folder/file  e.g. python manage.py test t2
                                      python manage.py test test_schema.py
  psql      open a SQL prompt inside the database
"""
import os
import pathlib
import subprocess
import sys

import psycopg
from dotenv import load_dotenv

# ---- 1. Read the settings from .env ------------------------------------
ROOT = pathlib.Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
USER = os.environ["POSTGRES_USER"]
PASSWORD = os.environ["POSTGRES_PASSWORD"]
DB = os.environ["POSTGRES_DB"]
HOST = os.environ.get("POSTGRES_HOST", "localhost")
PORT = os.environ.get("POSTGRES_PORT", "5432")
URL = f"postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB}"
MIGRATIONS = ROOT / "db" / "migrations"
SEED = ROOT / "db" / "seed" / "seed_minimal.sql"


def connect():
    return psycopg.connect(URL, autocommit=True)


def run_sql_file(conn, path):
    # utf-8-sig removes the invisible mark Windows sometimes adds at the start
    conn.execute(path.read_text(encoding="utf-8-sig"))


# ---- 2. Migrations: apply each SQL file once, in name order -------------
def ensure_log(conn):
    # this table remembers which files were already applied
    conn.execute(
        "CREATE TABLE IF NOT EXISTS public.schema_migrations ("
        " filename text PRIMARY KEY,"
        " applied_at timestamptz NOT NULL DEFAULT now())"
    )


def applied(conn):
    return {row[0] for row in conn.execute("SELECT filename FROM public.schema_migrations")}


def migrate():
    files = sorted(MIGRATIONS.glob("*.sql"))
    with connect() as conn:
        ensure_log(conn)
        new = [f for f in files if f.name not in applied(conn)]
        if not new:
            print("Database is up to date.")
            return
        for f in new:
            # each file runs in one transaction: all of it is applied, or none of it
            try:
                with conn.transaction():
                    run_sql_file(conn, f)
                    conn.execute("INSERT INTO public.schema_migrations (filename) VALUES (%s)", (f.name,))
            except psycopg.Error as e:
                print(f"FAILED {f.name}: {e}")
                print("Nothing from this file was applied. Fix it and run migrate again.")
                sys.exit(1)
            print("applied", f.name)


def status():
    files = sorted(MIGRATIONS.glob("*.sql"))
    with connect() as conn:
        ensure_log(conn)
        done = applied(conn)
    for f in files:
        print(("  applied  " if f.name in done else "  PENDING  ") + f.name)
    if not files:
        print("No migration files yet.")


# ---- 3. Starter data and reset ------------------------------------------
def seed():
    if not SEED.exists():
        print("No seed file yet:", SEED.relative_to(ROOT))
        return
    with connect() as conn, conn.transaction():
        run_sql_file(conn, SEED)
    print("seeded", SEED.name)


def reset():
    with connect() as conn:
        conn.execute("DROP SCHEMA IF EXISTS core, staging CASCADE")
        conn.execute("DROP TABLE IF EXISTS public.schema_migrations")
    print("database cleared")
    migrate()
    seed()


# ---- 4. Tests ------------------------------------------------------------
def test(args):
    target = [str(ROOT / "tests" / a) for a in args] or [str(ROOT / "tests")]
    sys.exit(subprocess.run([sys.executable, "-m", "pytest", "-v", *target]).returncode)


# ---- 5. Choose the command ----------------------------------------------
def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "up":
        subprocess.run(["docker", "compose", "up", "-d"], check=True)
    elif cmd == "down":
        subprocess.run(["docker", "compose", "down"], check=True)
    elif cmd == "migrate":
        migrate()
    elif cmd == "status":
        status()
    elif cmd == "seed":
        seed()
    elif cmd == "reset":
        reset()
    elif cmd == "test":
        test(sys.argv[2:])
    elif cmd == "psql":
        subprocess.run(["docker", "compose", "exec", "db", "psql", "-U", USER, "-d", DB])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()