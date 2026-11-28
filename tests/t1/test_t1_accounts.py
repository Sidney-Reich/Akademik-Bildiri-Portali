"""BR-10 (emails) and BR-11 (ORCID)."""
import uuid

from .conftest import refused


def email():
    return f"{uuid.uuid4().hex}@test.edu"


def test_second_primary_email_refused(data):
    pid = data.person()
    with refused("idx_t1_one_primary_email"):
        data.run("INSERT INTO core.person_email VALUES (%s, %s, true)", (email(), pid))
    data.run("INSERT INTO core.person_email VALUES (%s, %s, false)", (email(), pid))


def test_removing_the_primary_email_refused(data):
    pid = data.person()
    data.run("INSERT INTO core.person_email VALUES (%s, %s, false)", (email(), pid))
    with refused("br10_primary_email"):
        data.run("DELETE FROM core.person_email WHERE person_id = %s AND is_primary", (pid,))


def test_account_without_email_refused(data):
    with refused("br10_primary_email"):
        data.run("INSERT INTO core.person (full_name, password_hash) VALUES ('X', 'hash')")


def test_imported_person_without_email_accepted(data):
    data.run("INSERT INTO core.person (full_name) VALUES ('Imported author')")


def test_used_email_refused(data):
    address, other = email(), data.person()
    data.run("INSERT INTO core.person_email VALUES (%s, %s, false)", (address, data.person()))
    with refused("person_email_pkey"):
        data.run("INSERT INTO core.person_email VALUES (%s, %s, false)", (address, other))
    with refused("person_email_email_check"):  # same address in capitals
        data.run("INSERT INTO core.person_email VALUES (%s, %s, false)", (address.upper(), other))


def test_duplicate_orcid_refused_but_empty_allowed(data):
    sql = "INSERT INTO core.person (full_name, orcid) VALUES ('X', %s)"
    data.run(sql, ("0000-0002-1825-0097",))
    with refused("person_orcid_key"):
        data.run(sql, ("0000-0002-1825-0097",))
    data.run(sql, (None,))
    data.run(sql, (None,))
