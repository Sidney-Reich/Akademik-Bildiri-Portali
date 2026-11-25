"""Schema contract test (Report 4.1).

Every table file in db/migrations must create its tables exactly as the
report describes them: the table exists in the `core` schema, it has the
report's columns, its primary key, its foreign keys and its unique keys.

A table is checked as soon as its file exists (e.g. 002_t2_conference.sql).
Tables of files that nobody has written yet are skipped, not failed.

Run:  python manage.py test test_schema.py
"""
import pathlib

import pytest

MIGRATIONS = pathlib.Path(__file__).resolve().parents[1] / "db" / "migrations"

# table -> (file prefix, columns, primary key, foreign keys, unique keys)
# foreign key: (columns...) -> referenced table
EXPECTED = {
    # ---- 001_t1_people.sql (Eyup) -------------------------------------
    "person": ("001",
        {"person_id", "full_name", "orcid", "password_hash", "created_at"},
        ("person_id",), {}, [("orcid",)]),
    "person_email": ("001",
        {"email", "person_id", "is_primary"},
        ("email",), {("person_id",): "person"}, []),
    "institution": ("001",
        {"institution_id", "name", "country"},
        ("institution_id",), {}, []),

    # ---- 002_t2_conference.sql (Kadir) --------------------------------
    "conference": ("002",
        {"conference_id", "name", "year", "created_by"},
        ("conference_id",), {("created_by",): "person"}, []),
    "conference_policy": ("002",
        {"conference_id", "valid_from", "k", "l", "n", "max_revision_rounds", "changed_by"},
        ("conference_id", "valid_from"),
        {("conference_id",): "conference", ("changed_by",): "person"}, []),
    "conference_member": ("002",
        {"conference_id", "person_id", "role", "invitation_status", "invite_token_hash",
         "token_expires_at", "invited_at", "responded_at", "personal_max_load"},
        ("conference_id", "person_id"),
        {("conference_id",): "conference", ("person_id",): "person"}, []),
    "track": ("002",
        {"track_id", "conference_id", "name"},
        ("track_id",), {("conference_id",): "conference"}, []),
    "track_deadline": ("002",
        {"track_id", "deadline_type", "valid_from", "due_at", "changed_by"},
        ("track_id", "deadline_type", "valid_from"),
        {("track_id",): "track", ("changed_by",): "person"}, []),
    "declared_conflict": ("002",
        {"person_a", "person_b", "reason", "declared_at"},
        ("person_a", "person_b"),
        {("person_a",): "person", ("person_b",): "person"}, []),

    # ---- 003_t1_submission.sql (Eyup) ---------------------------------
    "submission": ("003",
        {"submission_id", "track_id", "title", "abstract", "status", "idempotency_key",
         "corresponding_author_id", "created_at"},
        ("submission_id",),
        {("track_id",): "track",
         ("submission_id", "corresponding_author_id"): "authorship"},
        [("idempotency_key",)]),
    "submission_version": ("003",
        {"submission_id", "version_no", "file_path", "file_hash", "uploaded_at"},
        ("submission_id", "version_no"), {("submission_id",): "submission"}, []),
    "authorship": ("003",
        {"submission_id", "person_id", "author_order", "contribution_share", "institution_id"},
        ("submission_id", "person_id"),
        {("submission_id",): "submission", ("person_id",): "person",
         ("institution_id",): "institution"}, []),

    # ---- 004_t3_topics_publications.sql (Sidney) ----------------------
    "topic": ("004",
        {"topic_id", "name", "acronym"},
        ("topic_id",), {}, []),
    "reviewer_topic": ("004",
        {"person_id", "topic_id"},
        ("person_id", "topic_id"), {("person_id",): "person", ("topic_id",): "topic"}, []),
    "submission_topic": ("004",
        {"submission_id", "topic_id"},
        ("submission_id", "topic_id"),
        {("submission_id",): "submission", ("topic_id",): "topic"}, []),
    "publication": ("004",
        {"publication_id", "title", "year", "source"},
        ("publication_id",), {}, []),
    "publication_author": ("004",
        {"publication_id", "person_id"},
        ("publication_id", "person_id"),
        {("publication_id",): "publication", ("person_id",): "person"}, []),
    "criterion": ("004",
        {"criterion_id", "conference_id", "name", "min_score", "max_score"},
        ("criterion_id",), {("conference_id",): "conference"}, []),

    # ---- 005_t2_assignment.sql (Kadir) --------------------------------
    "review_assignment": ("005",
        {"assignment_id", "submission_id", "reviewer_id", "round", "is_additional",
         "reason", "assigned_by", "status"},
        ("assignment_id",),
        {("submission_id",): "submission", ("reviewer_id",): "person",
         ("assigned_by",): "person"},
        [("submission_id", "reviewer_id", "round")]),

    # ---- 006_t3_review.sql (Sidney) -----------------------------------
    "review": ("006",
        {"assignment_id", "version_no", "recommendation", "confidence", "submitted_at"},
        ("assignment_id",), {("assignment_id",): "review_assignment"}, []),
    "review_score": ("006",
        {"assignment_id", "criterion_id", "score"},
        ("assignment_id", "criterion_id"),
        {("assignment_id",): "review", ("criterion_id",): "criterion"}, []),

    # ---- 007_t4_decision_audit.sql (Selim) ----------------------------
    "status_transition": ("007",
        {"from_status", "to_status"},
        ("from_status", "to_status"), {}, []),
    "decision": ("007",
        {"submission_id", "round", "type", "decided_by", "justification", "decided_at"},
        ("submission_id", "round"),
        {("submission_id",): "submission", ("decided_by",): "person"}, []),
    "notification": ("007",
        {"notification_id", "person_id", "type", "entity_type", "entity_id", "created_at"},
        ("notification_id",), {("person_id",): "person"}, []),
    "audit_log": ("007",
        {"log_id", "actor_id", "action", "entity_type", "entity_id", "old_value",
         "new_value", "created_at"},
        ("log_id",), {("actor_id",): "person"}, []),
}

FILES = {
    "001": "001_t1_people.sql", "002": "002_t2_conference.sql",
    "003": "003_t1_submission.sql", "004": "004_t3_topics_publications.sql",
    "005": "005_t2_assignment.sql", "006": "006_t3_review.sql",
    "007": "007_t4_decision_audit.sql",
}

# PostgreSQL's own catalog: unique keys (including the primary key) of a table
KEYS_SQL = """
SELECT i.indisprimary,
       ARRAY(SELECT a.attname FROM unnest(i.indkey) WITH ORDINALITY k(n, o)
             JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.n
             ORDER BY k.o)::text[]
FROM pg_index i
JOIN pg_class c ON c.oid = i.indrelid
JOIN pg_namespace s ON s.oid = c.relnamespace
WHERE s.nspname = 'core' AND c.relname = %s AND i.indisunique
"""

# PostgreSQL's own catalog: foreign keys of a table and the table they point to
FK_SQL = """
SELECT ARRAY(SELECT a.attname FROM unnest(con.conkey) WITH ORDINALITY k(n, o)
             JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.n
             ORDER BY k.o)::text[],
       ref.relname
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace s ON s.oid = c.relnamespace
JOIN pg_class ref ON ref.oid = con.confrelid
WHERE con.contype = 'f' AND s.nspname = 'core' AND c.relname = %s
"""


def file_written(prefix):
    return any(MIGRATIONS.glob(prefix + "_*.sql"))


def test_table_count_is_25():
    assert len(EXPECTED) == 25


@pytest.mark.parametrize("table", sorted(EXPECTED, key=lambda t: EXPECTED[t][0]))
def test_table_matches_report(conn, table):
    prefix, columns, pk, fks, uniques = EXPECTED[table]
    if not file_written(prefix):
        pytest.skip(f"{FILES[prefix]} not written yet")

    # 1. the table exists and 2. has the report's columns
    found = {r[0] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'core' AND table_name = %s", (table,))}
    assert found, f"core.{table} does not exist (expected in {FILES[prefix]})"
    missing = columns - found
    assert not missing, f"core.{table} is missing columns: {sorted(missing)}"

    # 3. primary key
    keys = conn.execute(KEYS_SQL, (table,)).fetchall()
    pks = [tuple(cols) for is_pk, cols in keys if is_pk]
    assert pks, f"core.{table} has no primary key; expected {pk}"
    assert set(pks[0]) == set(pk), f"core.{table} primary key is {pks[0]}; expected {pk}"

    # 4. unique keys
    unique_sets = {frozenset(cols) for _, cols in keys}
    for u in uniques:
        assert frozenset(u) in unique_sets, f"core.{table} needs UNIQUE {u}"

    # 5. foreign keys
    found_fks = {(frozenset(cols), ref) for cols, ref in conn.execute(FK_SQL, (table,))}
    for cols, ref in fks.items():
        assert (frozenset(cols), ref) in found_fks, \
            f"core.{table} needs FOREIGN KEY {cols} REFERENCES core.{ref}"