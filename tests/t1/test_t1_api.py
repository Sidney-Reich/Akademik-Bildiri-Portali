"""The backend on top of the rules: accounts, PDF checks (BR-09), submission."""
import io
import json
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

from backend import cleanup_orphans
from backend.app import db, files
from backend.app.main import app


@pytest.fixture
def client(db_url, monkeypatch, tmp_path):
    monkeypatch.setattr(db, "URL", db_url)
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    return TestClient(app)


def pdf(width=None, secret="Secret Author"):
    """A one-page PDF that carries the author's name in its hidden data."""
    writer = PdfWriter()
    page = writer.add_blank_page(width or uuid.uuid4().int % 100000 / 100 + 100, 300)
    writer.add_metadata({"/Author": secret})
    xmp = DecodedStreamObject()
    xmp.set_data(f"<x:xmpmeta>{secret}</x:xmpmeta>".encode())
    page[NameObject("/Metadata")] = writer._add_object(xmp)
    writer.root_object[NameObject("/Metadata")] = writer._add_object(xmp.clone(writer, True))
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def register(client, name="Ann"):
    address = f"{uuid.uuid4().hex}@test.edu"
    r = client.post("/auth/register", json={
        "full_name": name, "email": address, "password": "long password"})
    assert r.status_code == 201, r.text
    return address, {"Authorization": f"Bearer {r.json()['token']}"}


def send(client, auth, track, address, content=None, key=None, authors=None, name="p.pdf"):
    authors = authors or [{"email": address, "share": 100, "corresponding": True}]
    return client.post(
        "/submissions",
        headers={**auth, "Idempotency-Key": str(key or uuid.uuid4())},
        data={"title": "T", "abstract": "A", "track_id": track, "authors": json.dumps(authors)},
        files={"file": (name, content or pdf(), "application/pdf")})


def stored(tmp_path):
    return sorted(p.name for p in tmp_path.rglob("*.pdf"))


# ---- accounts ------------------------------------------------------------
def test_register_login_and_emails(client, data):
    address, auth = register(client)
    assert data.one("SELECT password_hash FROM core.person p JOIN core.person_email e "
                    "USING (person_id) WHERE email = %s", (address,)).startswith("$2b$")
    assert client.post("/auth/login", json={"email": address.upper(),
                                            "password": "long password"}).status_code == 200
    assert client.post("/auth/login", json={"email": address,
                                            "password": "wrong"}).status_code == 401
    assert client.post("/auth/register", json={"full_name": "B", "email": address,
                                               "password": "long password"}).status_code == 409
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer 1.9999999999.x"}).status_code == 401

    second = f"{uuid.uuid4().hex}@test.edu"
    assert client.post("/me/emails", headers=auth, json={"email": second}).status_code == 201
    assert client.put("/me/emails/primary", headers=auth, json={"email": second}).status_code == 200
    assert client.put("/me/emails/primary", headers=auth,
                      json={"email": "no@test.edu"}).status_code == 404
    assert client.get("/me", headers=auth).json()["emails"][0] == {
        "email": second, "is_primary": True}


def test_remove_email(client, data):
    address, auth = register(client)
    _, stranger = register(client)
    second = f"{uuid.uuid4().hex}@test.edu"
    client.post("/me/emails", headers=auth, json={"email": second})
    remove = lambda who, mail: client.delete("/me/emails", headers=who, params={"email": mail})
    assert remove(stranger, second).status_code == 404
    assert remove(auth, address).status_code == 409  # the primary one stays
    assert remove(auth, second).status_code == 200
    assert [e["email"] for e in client.get("/me", headers=auth).json()["emails"]] == [address]


# ---- BR-09 files ---------------------------------------------------------
def test_metadata_is_removed_and_result_is_stable():
    original = pdf(width=200)
    assert b"Secret Author" in original
    cleaned = files.clean_pdf(original)
    assert b"Secret Author" not in cleaned
    assert files.clean_pdf(original) == cleaned


def test_renamed_docx_refused(client, data, tmp_path):
    address, auth = register(client)
    docx = io.BytesIO()
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("word/document.xml", "<w/>")
    r = send(client, auth, data.track(), address, content=docx.getvalue(), name="paper.pdf")
    assert r.status_code == 422 and "PDF değil" in r.json()["detail"]
    assert stored(tmp_path) == []


def test_too_large_pdf_refused(client, data, tmp_path):
    address, auth = register(client)
    big = pdf() + b"\0" * (1024 * 1024)
    r = send(client, auth, data.track(max_mb=1), address, content=big)
    assert r.status_code == 413
    assert stored(tmp_path) == []


# ---- submission ----------------------------------------------------------
def test_submit_with_coauthor_and_list(client, data, tmp_path):
    address, auth = register(client)
    other = f"{uuid.uuid4().hex}@test.edu"
    r = send(client, auth, data.track(), address, authors=[
        {"email": address, "share": 60, "corresponding": True, "institution": "Uni A"},
        {"email": other, "full_name": "Bob", "share": 40}])
    assert r.status_code == 201, r.text
    [mine] = client.get("/submissions/mine", headers=auth).json()
    assert mine["status"] == "SUBMITTED" and mine["latest_version"] == 1
    assert [a["share"] for a in mine["authors"]] == [60, 40]
    assert len(stored(tmp_path)) == 1


def test_wrong_shares_and_late_submission_refused(client, data, tmp_path):
    address, auth = register(client)
    r = send(client, auth, data.track(), address,
             authors=[{"email": address, "share": 90, "corresponding": True}])
    assert r.status_code == 422 and "toplamı 90" in r.json()["detail"]
    r = send(client, auth, data.track(due="-1 minute"), address)
    assert r.status_code == 409 and "son tarihi" in r.json()["detail"]
    assert stored(tmp_path) == []


def test_three_identical_requests_at_once(client, data, tmp_path):
    address, auth = register(client)
    track, key, content = data.track(), uuid.uuid4(), pdf()
    authors = [{"email": address, "share": 50, "corresponding": True},
               {"email": f"{key.hex}@test.edu", "full_name": "New", "share": 50}]
    with ThreadPoolExecutor(3) as pool:
        results = list(pool.map(
            lambda _: send(client, auth, track, address, content, key, authors), range(3)))
    assert sorted(r.status_code for r in results) == [200, 200, 201], [r.text for r in results]
    assert len({r.json()["submission_id"] for r in results}) == 1
    assert data.count("submission", "idempotency_key", key) == 1
    assert len(stored(tmp_path)) == 1


def test_retry_after_deadline_returns_the_first_answer(client, data):
    address, auth = register(client)
    track, key = data.track(), uuid.uuid4()
    first = send(client, auth, track, address, key=key)
    data.deadline(track, "SUBMISSION", "-1 minute")
    again = send(client, auth, track, address, key=key)
    assert again.status_code == 200
    assert again.json()["submission_id"] == first.json()["submission_id"]


def test_crash_before_commit_leaves_no_rows_and_no_file(client, data, tmp_path, monkeypatch):
    address, auth = register(client)
    key = uuid.uuid4()
    real = files.PendingFile.publish

    def publish_then_crash(self):
        real(self)
        raise RuntimeError("crash")

    monkeypatch.setattr(files.PendingFile, "publish", publish_then_crash)
    with pytest.raises(RuntimeError):
        send(client, auth, data.track(), address, key=key)
    assert data.count("submission", "idempotency_key", key) == 0
    assert stored(tmp_path) == []


def test_same_pdf_twice_keeps_the_first_file(client, data, tmp_path):
    address, auth = register(client)
    track, content = data.track(), pdf()
    assert send(client, auth, track, address, content).status_code == 201
    r = send(client, auth, track, address, content)
    assert r.status_code == 409 and "daha önce gönderilmiş" in r.json()["detail"]
    assert len(stored(tmp_path)) == 1


def test_versions_authors_and_withdraw(client, data):
    address, auth = register(client)
    _, stranger = register(client)
    track = data.track()
    sid = send(client, auth, track, address).json()["submission_id"]
    url = f"/submissions/{sid}"
    new = {"file": ("v2.pdf", pdf(), "application/pdf")}

    assert client.post(url + "/versions", headers=stranger, files=new).status_code == 404
    assert client.post(url + "/versions", headers=auth, files=new).json()["version_no"] == 2
    assert client.post(url + "/versions", headers=auth, files=new).json()["repeated"] is True

    authors = [{"email": address, "share": 70, "corresponding": True},
               {"email": f"{uuid.uuid4().hex}@test.edu", "full_name": "Co", "share": 30}]
    assert client.put(url + "/authors", headers=auth, json=authors).status_code == 200
    assert client.get("/submissions/mine", headers=auth).json()[0]["can_upload"] is True
    data.deadline(track, "SUBMISSION", "-1 minute")
    assert client.get("/submissions/mine", headers=auth).json()[0]["can_upload"] is False
    assert client.put(url + "/authors", headers=auth, json=[
        {**authors[0], "share": 100}]).status_code == 409
    assert data.count("authorship", "submission_id", sid) == 2
    assert data.one("SELECT count(*) FROM core.audit_log WHERE entity_id = %s "
                    "AND actor_id IS NOT NULL", (sid,)) == 1

    assert client.post(url + "/withdraw", headers=auth).json()["status"] == "WITHDRAWN"
    assert client.post(url + "/versions", headers=auth,
                       files={"file": ("v3.pdf", pdf(), "application/pdf")}).status_code == 409


def test_only_authors_can_open_the_pdf(client, data):
    address, auth = register(client)
    _, stranger = register(client)
    sid = send(client, auth, data.track(), address).json()["submission_id"]
    url = f"/submissions/{sid}/versions/1/file"
    r = client.get(url, headers=auth)
    assert r.status_code == 200 and r.content.startswith(b"%PDF-")
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("inline")
    assert client.get(url, headers=stranger).status_code == 404
    assert client.get(url).status_code == 401
    assert client.get(f"/submissions/{sid}/versions/2/file", headers=auth).status_code == 404


def test_revised_version_changes_status(client, data):
    address, auth = register(client)
    track, content = data.track(), pdf()
    sid = send(client, auth, track, address, content).json()["submission_id"]
    for status in ("UNDER_REVIEW", "REVISION_REQUESTED"):
        data.run("UPDATE core.submission SET status = %s WHERE submission_id = %s", (status, sid))
    data.deadline(track, "REVISION", "1 day")
    url = f"/submissions/{sid}/versions"
    same = client.post(url, headers=auth, files={"file": ("a.pdf", content, "application/pdf")})
    assert same.status_code == 422
    r = client.post(url, headers=auth, files={"file": ("b.pdf", pdf(), "application/pdf")})
    assert r.json() == {"version_no": 2, "status": "REVISED", "repeated": False}


def test_cleanup_removes_only_orphans(client, data, tmp_path):
    address, auth = register(client)
    send(client, auth, data.track(), address)
    kept = stored(tmp_path)
    (tmp_path / ("f" * 64 + ".pdf")).write_bytes(b"orphan")
    assert cleanup_orphans.cleanup() == []          # too young
    assert len(cleanup_orphans.cleanup(min_age=0)) == 1
    assert stored(tmp_path) == kept
