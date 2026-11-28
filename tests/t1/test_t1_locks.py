"""BR-08 (author list lock), BR-27 and BR-28 (versions)."""
import uuid

import pytest

from .conftest import refused


def attempts(data, sid):
    return data.one("SELECT count(*) FROM core.audit_log "
                    "WHERE action = 'AUTHORSHIP_CHANGE_REFUSED' AND entity_id = %s", (sid,))


def authors(data, sid):
    return data.run("SELECT person_id, contribution_share FROM core.authorship "
                    "WHERE submission_id = %s ORDER BY author_order", (sid,))


def closed_submission(data):
    """A submission made in time, whose deadline has passed since."""
    track, first, second = data.track(), data.person(), data.person()
    sid = data.submit(track=track, authors=[(first, 60), (second, 40)])
    data.deadline(track, "SUBMISSION", "-1 minute")
    return sid, track, first, second


def set_status(data, sid, *path):
    for status in path:  # step by step, as the state machine allows
        data.run("UPDATE core.submission SET status = %s WHERE submission_id = %s", (status, sid))


# ---- BR-08 ---------------------------------------------------------------
def test_adding_author_after_deadline_refused_and_recorded(data):
    sid, *_ = closed_submission(data)
    changed = data.run("INSERT INTO core.authorship VALUES (%s, %s, 3, 1)", (sid, data.person()))
    assert changed == 0
    assert len(authors(data, sid)) == 2
    assert attempts(data, sid) == 1


def test_changing_and_removing_authors_after_deadline_refused(data):
    sid, _, first, second = closed_submission(data)
    before = authors(data, sid)
    assert data.run("UPDATE core.authorship SET contribution_share = 50 "
                    "WHERE submission_id = %s", (sid,)) == 0
    assert data.run("DELETE FROM core.authorship WHERE submission_id = %s", (sid,)) == 0
    data.run("UPDATE core.submission SET corresponding_author_id = %s "
             "WHERE submission_id = %s", (second, sid))
    assert authors(data, sid) == before
    assert data.one("SELECT corresponding_author_id FROM core.submission "
                    "WHERE submission_id = %s", (sid,)) == first
    assert attempts(data, sid) == 5


def test_authors_can_change_before_deadline(data):
    first, second = data.person(), data.person()
    sid = data.submit(authors=[(first, 100)])
    with data.connect() as c:
        c.execute("UPDATE core.authorship SET contribution_share = 70 "
                  "WHERE submission_id = %s", (sid,))
        c.execute("INSERT INTO core.authorship VALUES (%s, %s, 2, 30)", (sid, second))
    assert len(authors(data, sid)) == 2
    assert attempts(data, sid) == 0


def test_authors_locked_during_review_even_before_deadline(data):
    sid = data.submit()
    set_status(data, sid, "UNDER_REVIEW")
    assert data.run("DELETE FROM core.authorship WHERE submission_id = %s", (sid,)) == 0
    assert attempts(data, sid) == 1


# ---- BR-27, BR-28 --------------------------------------------------------
def upload(data, sid, number):
    with data.connect() as c:
        data.insert_version(c, sid, number)


def revision_requested(data, due):
    track = data.track()
    sid = data.submit(track=track)
    set_status(data, sid, "UNDER_REVIEW", "REVISION_REQUESTED")
    if due:
        data.deadline(track, "REVISION", due)
    return sid, track


def test_revised_version_in_time_accepted(data):
    sid, _ = revision_requested(data, "1 day")
    upload(data, sid, 2)
    assert data.count("submission_version", "submission_id", sid) == 2


@pytest.mark.parametrize("due", ["-1 minute", None])
def test_late_revised_version_refused(data, due):
    sid, _ = revision_requested(data, due)
    with refused("br27_revision_deadline"):
        upload(data, sid, 2)


def test_no_upload_during_review(data):
    sid = data.submit()
    set_status(data, sid, "UNDER_REVIEW")
    with refused("br28_upload_status"):
        upload(data, sid, 2)


def test_final_version_after_accept(data):
    track = data.track()
    sid = data.submit(track=track)
    set_status(data, sid, "UNDER_REVIEW", "ACCEPTED")
    data.deadline(track, "CAMERA_READY", "-1 minute")
    with refused("br27_camera_ready_deadline"):
        upload(data, sid, 2)
    data.deadline(track, "CAMERA_READY", "1 day")
    upload(data, sid, 2)


def test_version_numbers_have_no_gaps(data):
    sid = data.submit()
    with refused("br28_version_order"):
        upload(data, sid, 3)


@pytest.mark.parametrize("sql", [
    "UPDATE core.submission_version SET file_hash = repeat('a', 64) WHERE submission_id = %s",
    "DELETE FROM core.submission_version WHERE submission_id = %s",
])
def test_old_version_cannot_change(data, sql):
    sid = data.submit()
    with refused("br28_immutable"):
        data.run(sql, (sid,))


def test_versions_cannot_be_truncated(data):
    data.submit()
    # CASCADE: T3's review table may later point here
    with refused("br28_immutable"):
        data.run("TRUNCATE core.submission_version CASCADE")
