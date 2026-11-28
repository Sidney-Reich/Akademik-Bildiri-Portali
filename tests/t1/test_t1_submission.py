"""BR-01 to BR-07: tested directly on the database."""
import threading
import uuid

import psycopg
import pytest

from .conftest import refused


# ---- BR-01 track ---------------------------------------------------------
def test_no_track_or_unknown_track_refused(data):
    author = data.person()
    with pytest.raises(psycopg.errors.NotNullViolation):
        with data.connect() as c:
            data.insert_submission(c, None, [(author, 100)])
    with refused("submission_track_id_fkey"):
        data.submit(track=999999, authors=[(author, 100)])


def test_track_cannot_be_changed(data):
    sid = data.submit()
    with refused("br01_fixed_columns"):
        data.run("UPDATE core.submission SET track_id = %s WHERE submission_id = %s",
                 (data.track(), sid))


# ---- BR-02 corresponding author -----------------------------------------
def test_corresponding_author_must_be_an_author(data):
    with refused("fk_t1_corresponding_author"):
        data.submit(corresponding=data.person("not an author"))


def test_submission_without_authors_refused(data):
    track, person = data.track(), data.person()
    with refused("fk_t1_corresponding_author"):
        with data.connect() as c:
            sid = c.execute(
                "INSERT INTO core.submission (track_id, title, abstract, idempotency_key, "
                "corresponding_author_id) VALUES (%s, 'T', 'A', %s, %s) RETURNING submission_id",
                (track, uuid.uuid4(), person)).fetchone()[0]
            data.insert_version(c, sid, 1)


# ---- BR-03 shares --------------------------------------------------------
def test_shares_60_30_refused_at_commit(data):
    authors = [(data.person(), 60), (data.person(), 30)]
    with pytest.raises(psycopg.errors.CheckViolation, match="total 90.00; must be 100"):
        data.submit(authors=authors)


def test_share_zero_refused(data):
    with refused("authorship_contribution_share_check"):
        data.submit(authors=[(data.person(), 100), (data.person(), 0)])


def test_shares_60_40_accepted(data):
    sid = data.submit(authors=[(data.person(), 60), (data.person(), 40)])
    assert data.count("authorship", "submission_id", sid) == 2


def test_changing_one_share_refused(data):
    first = data.person()
    sid = data.submit(authors=[(first, 60), (data.person(), 40)])
    with refused("br03_share_total"):
        data.run("UPDATE core.authorship SET contribution_share = 70 "
                 "WHERE submission_id = %s AND person_id = %s", (sid, first))


# ---- BR-04 deadline ------------------------------------------------------
def test_late_submission_refused_then_accepted_after_extension(data):
    track = data.track(due="-1 hour")
    with refused("br04_deadline"):
        data.submit(track=track)
    data.deadline(track, "SUBMISSION", "1 hour")  # a new row; the old one stays
    assert data.submit(track=track)
    assert data.count("track_deadline", "track_id", track) == 2


def test_grace_period(data):
    assert data.submit(track=data.track(due="-5 minutes", grace=10))
    with refused("br04_deadline"):
        data.submit(track=data.track(due="-15 minutes", grace=10))


def test_track_without_deadline_is_closed(data):
    with refused("br04_deadline"):
        data.submit(track=data.track(due=None))


def at_arrival(data, track, ago):
    author = data.person()
    with data.connect() as c:
        c.execute("SELECT set_config('app.request_received_at', "
                  "(now() - %s::interval)::text, true)", (ago,))
        return data.insert_submission(c, track, [(author, 100)])


def test_arrival_time_counts_not_processing_time(data):
    # arrived 2 minutes ago, deadline passed 1 minute ago
    assert at_arrival(data, data.track(due="-1 minute"), "2 minutes")


def test_forged_old_arrival_time_refused(data):
    with refused("br04_request_time"):
        at_arrival(data, data.track(due="-1 day"), "2 days")


def test_given_created_at_is_ignored(data):
    track, author = data.track(due="-1 hour"), data.person()
    with refused("br04_deadline"):
        data.run("INSERT INTO core.submission (track_id, title, abstract, idempotency_key, "
                 "corresponding_author_id, created_at) VALUES (%s, 'T', 'A', %s, %s, "
                 "now() - interval '2 days')", (track, uuid.uuid4(), author))


# ---- BR-05 repeated requests --------------------------------------------
def test_same_request_three_times_gives_one_submission(data):
    track, key = data.track(), uuid.uuid4()
    data.submit(track=track, key=key)
    for _ in range(2):
        with refused("submission_idempotency_key_key"):
            data.submit(track=track, key=key)
    assert data.count("submission", "idempotency_key", key) == 1


# ---- BR-06 all or nothing -----------------------------------------------
def test_crash_during_submission_saves_nothing(data):
    track, author, key = data.track(), data.person(), uuid.uuid4()
    c = data.connect()
    data.insert_submission(c, track, [(author, 100)], key=key)
    data.run("SELECT pg_terminate_backend(%s)", (c.info.backend_pid,))  # the crash
    with pytest.raises(psycopg.OperationalError):
        c.commit()
    c.close()
    assert data.count("submission", "idempotency_key", key) == 0
    assert data.count("authorship", "person_id", author) == 0


def test_submission_without_file_refused(data):
    with refused("br06_requires_version"):
        data.submit(with_version=False)


# ---- BR-07 same PDF ------------------------------------------------------
def test_same_pdf_in_same_conference_refused(data):
    conf, file_hash = data.conference(), uuid.uuid4().hex * 2
    data.submit(track=data.track(conf), file_hash=file_hash)
    with refused("br07_unique_pdf"):
        data.submit(track=data.track(conf), file_hash=file_hash)  # another track too
    assert data.submit(track=data.track(), file_hash=file_hash)   # another conference


def test_same_pdf_at_the_same_moment(data):
    conf, file_hash = data.conference(), uuid.uuid4().hex * 2
    track = data.track(conf)
    first, second = data.person(), data.person()
    errors = []

    def other():
        try:
            data.submit(track=track, authors=[(second, 100)], file_hash=file_hash)
        except psycopg.Error as e:
            errors.append(e.diag.constraint_name)

    with data.connect() as c:
        data.insert_submission(c, track, [(first, 100)], file_hash=file_hash)
        thread = threading.Thread(target=other)
        thread.start()
        thread.join(0.5)
        assert thread.is_alive(), "the second upload should be waiting"
    thread.join(10)
    assert errors == ["br07_unique_pdf"]
