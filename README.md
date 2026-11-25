# Academic Paper Review Portal (YMH303)

Database project for a university conference review system. The business rules
(BR-01 … BR-29) are enforced by **PostgreSQL itself**; the backend and the screens sit on top.

| Member | Task                                         | Test folder |
| ------ | -------------------------------------------- | ----------- |
| Eyup   | T1. Accounts and paper submission            | `tests/t1`  |
| Kadir  | T2. Conference setup and reviewer assignment | `tests/t2`  |
| Sidney | T3. Blind review, access security and data   | `tests/t3`  |
| Selim  | T4. Decisions, audit log and integration     | `tests/t4`  |

---

## 1. Setup (once, about 15 minutes)

You need: **Git**, **Docker Desktop** (running), **Python 3.11+**, **VS Code**.
Commands below are for the VS Code terminal on Windows (PowerShell). On macOS/Linux,
use `cp` instead of `Copy-Item` and `source .venv/bin/activate` to activate.

```powershell
# 1. get the code
cd $HOME\Documents
git clone https://github.com/Sidney-Reich/Akademik-Bildiri-Portali.git
cd Akademik-Bildiri-Portali

# 2. your own settings file (never uploaded); you may change the password
Copy-Item .env.example .env

# 3. start PostgreSQL 19 in Docker
docker compose up -d
docker compose ps                     # STATUS must say "healthy"

# 4. Python environment and packages
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # the prompt now starts with (.venv)
pip install -r requirements.txt

# 5. build the database and run the tests
python manage.py migrate
python manage.py test
```

Then open the folder in VS Code: **File → Open Folder… → Akademik-Bildiri-Portali**.

**Problems?**

- `running scripts is disabled` → run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
- `password authentication failed` → another PostgreSQL is installed on your laptop and uses port 5432.
  Set `POSTGRES_PORT=5433` in your `.env`, then `docker compose up -d` again.
- Files appear in the wrong place → run `pwd`; you must be in the repository folder.

## 2. Every work session

```powershell
cd $HOME\Documents\Akademik-Bildiri-Portali
.\.venv\Scripts\Activate.ps1
docker compose up -d
git checkout main
git pull
python manage.py migrate
```

## 3. Commands

| Command                                 | What it does                                                            |
| --------------------------------------- | ----------------------------------------------------------------------- |
| `python manage.py migrate`              | applies new files from `db/migrations`                                  |
| `python manage.py status`               | lists applied and pending migration files                               |
| `python manage.py seed`                 | loads the starter data (`db/seed/seed_minimal.sql`)                     |
| `python manage.py reset`                | wipes the database, then migrate + seed (use it often)                  |
| `python manage.py test`                 | runs all tests; `test t2` runs one task, `test test_schema.py` one file |
| `python manage.py psql`                 | SQL prompt inside the database (`\q` to leave)                          |
| `uvicorn backend.app.main:app --reload` | starts the backend; open http://127.0.0.1:8000/docs                     |

To browse tables and run SQL in VS Code, install the **PostgreSQL** extension (by Microsoft)
and connect to `localhost`, port `5432`, database `portal`, user and password from your `.env`.

## 4. How we work

1. **Tables first (25–26 Nov).** Each member writes their own table files
   (`db/migrations/README.md` lists the order). A table file is merged only when
   `python manage.py test test_schema.py` passes for its tables.
2. **Then the rules (from 27 Nov).** One rule = one new migration file + a test that tries
   to break it.
3. **Branches.** Never work on `main`:
   ```
   git checkout -b t2/conference-tables
   ... work, then:
   git add .
   git commit -m "T2: conference tables (002)"
   git push -u origin t2/conference-tables
   ```
   Open a pull request on GitHub. It is merged when the tests pass (GitHub runs them
   automatically) and one teammate approves.
4. **Never edit a merged migration file**; add a new one.
5. **Names start with your task:** `trg_t1_…`, `fn_t2_…`, `v_t3_…`, `idx_t4_…`.
6. **Record every test result** in `tests/results.md`.

## 5. Folders

```
backend/        FastAPI application (backend/app/main.py)
db/migrations/  SQL files that create and change the database, applied in order
db/seed/        starter data shared by all tests
db/queries/     business queries
docs/           ER and EER diagrams (open with draw.io)
frontend/       screens
import/         DBLP import (T3)
tests/          test_schema.py (table contract), t1/ … t4/ (each member's tests)
manage.py       project commands
```
