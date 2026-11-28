"""T1 test setup.

Most T1 rules are checked at COMMIT, and some need two connections, so these
tests use their own temporary database (built from the migrations, dropped at
the end) and really commit. Your own database is not touched.
"""
import uuid

import psycopg
import pytest

import manage
from tests.conftest import URL

TEST_DB = "portal_t1_test"


@pytest.fixture(scope="session")
def db_url():
    admin = psycopg.connect(URL, autocommit=True)
    admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
    admin.execute(f"CREATE DATABASE {TEST_DB}")
    url = URL.rsplit("/", 1)[0] + "/" + TEST_DB
    old, manage.URL = manage.URL, url
    try:
        manage.migrate()
    finally:
        manage.URL = old
    with psycopg.connect(url) as c:
        # stand-in until T4's 007 file exists (columns of Report 4.1)
        if c.execute("SELECT to_regclass('core.audit_log')").fetchone()[0] is None:
            c.execute(
                "CREATE TABLE core.audit_log ("
                " log_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,"
                " actor_id bigint REFERENCES core.person, action text NOT NULL,"
                " entity_type text NOT NULL, entity_id bigint NOT NULL,"
                " old_value jsonb, new_value jsonb,"
                " created_at timestamptz NOT NULL DEFAULT now())")
    yield url
    admin.execute(f"DROP DATABASE {TEST_DB} WITH (FORCE)")
    admin.close()


class Data:
    """Small helpers that create the rows a test needs. Each call commits."""

    def __init__(self, url):
        self.url = url

    def connect(self):
        return psycopg.connect(self.url)

    def run(self, sql, params=None):
        with self.connect() as c:
            cur = c.execute(sql, params)
            return cur.fetchall() if cur.description else cur.rowcount

    def one(self, sql, params=None):
        return self.run(sql, params)[0][0]

    def person(self, name="Author"):
        with self.connect() as c:
            pid = c.execute("INSERT INTO core.person (full_name) VALUES (%s) RETURNING person_id",
                            (name,)).fetchone()[0]
            c.execute("INSERT INTO core.person_email VALUES (%s, %s, true)",
                      (f"{uuid.uuid4().hex}@test.edu", pid))
        return pid

    def conference(self, grace=0, max_mb=10):
        chair = self.person("Chair")
        with self.connect() as c:
            conf = c.execute("INSERT INTO core.conference (name, year, created_by) "
                             "VALUES ('Conf', 2027, %s) RETURNING conference_id",
                             (chair,)).fetchone()[0]
            c.execute("INSERT INTO core.conference_policy (conference_id, changed_by, "
                      "grace_minutes, max_pdf_mb) VALUES (%s, %s, %s, %s)",
                      (conf, chair, grace, max_mb))
        return conf

    def track(self, conf=None, due="1 day", **policy):
        """due: offset from now, e.g. '-1 hour'; None = no deadline."""
        conf = conf or self.conference(**policy)
        track = self.one("INSERT INTO core.track (conference_id, name) VALUES (%s, %s) "
                         "RETURNING track_id", (conf, uuid.uuid4().hex[:8]))
        if due is not None:
            self.deadline(track, "SUBMISSION", due)
        return track

    def deadline(self, track, kind, due):
        self.run("INSERT INTO core.track_deadline (track_id, deadline_type, due_at, changed_by) "
                 "SELECT track_id, %s, now() + %s::interval, c.created_by "
                 "FROM core.track t JOIN core.conference c USING (conference_id) "
                 "WHERE track_id = %s", (kind, due, track))

    def insert_submission(self, c, track, authors, corresponding=None, key=None,
                          file_hash=None, with_version=True):
        """All rows of one submission on an open connection (no commit)."""
        sid = c.execute(
            "INSERT INTO core.submission (track_id, title, abstract, idempotency_key, "
            "corresponding_author_id) VALUES (%s, 'Title', 'Abstract', %s, %s) "
            "RETURNING submission_id",
            (track, key or uuid.uuid4(), corresponding or authors[0][0])).fetchone()[0]
        for order, (person, share) in enumerate(authors, start=1):
            c.execute("INSERT INTO core.authorship VALUES (%s, %s, %s, %s)",
                      (sid, person, order, share))
        if with_version:
            self.insert_version(c, sid, 1, file_hash)
        return sid

    def insert_version(self, c, sid, number, file_hash=None):
        file_hash = file_hash or uuid.uuid4().hex * 2
        c.execute("INSERT INTO core.submission_version (submission_id, version_no, file_path, "
                  "file_hash) VALUES (%s, %s, %s, %s)",
                  (sid, number, f"{file_hash}.pdf", file_hash))

    def submit(self, track=None, authors=None, **kw):
        track = track or self.track()
        authors = authors or [(self.person(), 100)]
        with self.connect() as c:
            return self.insert_submission(c, track, authors, **kw)

    def count(self, table, column, value):
        return self.one(f"SELECT count(*) FROM core.{table} WHERE {column} = %s", (value,))


@pytest.fixture
def data(db_url):
    return Data(db_url)


def refused(constraint):
    """with refused('br03_share_total'): ...  -- the database must refuse."""
    class _Refused:
        def __enter__(self):
            self.ctx = pytest.raises(psycopg.errors.IntegrityError)
            self.info = self.ctx.__enter__()

        def __exit__(self, *exc):
            handled = self.ctx.__exit__(*exc)
            assert self.info.value.diag.constraint_name == constraint, self.info.value
            return handled

    return _Refused()
