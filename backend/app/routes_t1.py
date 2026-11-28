"""T1 (Eyup): accounts and paper submission.

The rules themselves live in the database (db/migrations/*_t1_*.sql). The checks
here only give a friendlier message before the database would refuse.
"""
import time
import uuid
from decimal import Decimal

import psycopg
from fastapi import (APIRouter, Depends, File, Form, Header, HTTPException, Request,
                     Response, UploadFile)
from fastapi.responses import FileResponse
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from . import db, files
from .auth import MAX_PASSWORD_BYTES, check_password, current_person, hash_password, make_token

router = APIRouter(tags=["T1 accounts and submission"])


def get_conn():
    return db.get_conn()


# database constraint -> message shown to the user (others: the database's own text)
MESSAGES = {
    "person_orcid_key": "Bu ORCID zaten kayıtlı.",
    "person_orcid_check": "ORCID 0000-0002-1825-0097 biçiminde olmalı.",
    "person_email_pkey": "Bu e-posta zaten kayıtlı.",
    "person_email_email_check": "Geçerli bir e-posta adresi değil.",
    "person_full_name_check": "Ad soyad boş olamaz.",
    "submission_track_id_fkey": "Böyle bir izlek yok.",
    "br03_share_total": "Katkı paylarının toplamı 100 olmalı.",
    "br04_deadline": "Bu izlek için gönderim son tarihi geçti veya belirlenmemiş.",
    "br04_request_time": "İstek zamanı doğrulanamadı; lütfen yeniden deneyin.",
    "br07_unique_pdf": "Bu PDF bu konferansa daha önce gönderilmiş.",
    "br27_revision_deadline": "Revizyon son tarihi geçti veya belirlenmemiş.",
    "br27_camera_ready_deadline": "Son sürüm yükleme tarihi geçti.",
    "br28_upload_status": "Bildiri bu durumdayken yeni sürüm yüklenemez.",
}


def db_error(e: psycopg.Error) -> HTTPException:
    """A refusal by the database becomes a readable (Turkish) 409."""
    if isinstance(e, (psycopg.errors.IntegrityError, psycopg.errors.DataError)):
        return HTTPException(409, MESSAGES.get(
            e.diag.constraint_name, f"Veritabanı işlemi reddetti: {e.diag.message_primary}"))
    raise e


def clean_email(email: str) -> str:
    email = email.strip().lower()
    if email.count("@") != 1 or any(c.isspace() for c in email) or not all(email.split("@")):
        raise HTTPException(422, f"'{email}' geçerli bir e-posta adresi değil.")
    return email


# ---- accounts ------------------------------------------------------------
class Register(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(max_length=254)
    password: str = Field(min_length=8)
    orcid: str | None = None


class Login(BaseModel):
    email: str
    password: str


class Email(BaseModel):
    email: str = Field(max_length=254)


@router.post("/auth/register", status_code=201)
def register(body: Register):
    email = clean_email(body.email)
    if len(body.password.encode()) > MAX_PASSWORD_BYTES:
        raise HTTPException(422, f"Parola {MAX_PASSWORD_BYTES} bayttan uzun olamaz.")
    if not body.full_name.strip():
        raise HTTPException(422, "Ad soyad gerekli.")
    password_hash = hash_password(body.password)
    try:
        with get_conn() as conn:
            person_id = conn.execute(
                "INSERT INTO core.person (full_name, orcid, password_hash) "
                "VALUES (%s, %s, %s) RETURNING person_id",
                (body.full_name.strip(), (body.orcid or "").strip() or None, password_hash),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO core.person_email (email, person_id, is_primary) "
                "VALUES (%s, %s, true)", (email, person_id))
    except psycopg.Error as e:
        raise db_error(e) from e
    return {"person_id": person_id, "token": make_token(person_id)}


@router.post("/auth/login")
def login(body: Login):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT p.person_id, p.password_hash FROM core.person p "
            "JOIN core.person_email e ON e.person_id = p.person_id WHERE e.email = %s",
            (body.email.strip().lower(),)).fetchone()
    if not check_password(body.password, row[1] if row else None):
        raise HTTPException(401, "E-posta veya parola hatalı.")
    return {"person_id": row[0], "token": make_token(row[0])}


@router.get("/me")
def me(person_id: int = Depends(current_person)):
    with get_conn() as conn:
        name, orcid = conn.execute(
            "SELECT full_name, orcid FROM core.person WHERE person_id = %s",
            (person_id,)).fetchone()
        emails = conn.execute(
            "SELECT email, is_primary FROM core.person_email WHERE person_id = %s "
            "ORDER BY is_primary DESC, email", (person_id,)).fetchall()
    return {"person_id": person_id, "full_name": name, "orcid": orcid,
            "emails": [{"email": e, "is_primary": p} for e, p in emails]}


@router.post("/me/emails", status_code=201)
def add_email(body: Email, person_id: int = Depends(current_person)):
    email = clean_email(body.email)
    try:
        with get_conn() as conn:
            conn.execute("INSERT INTO core.person_email (email, person_id) VALUES (%s, %s)",
                         (email, person_id))
    except psycopg.Error as e:
        raise db_error(e) from e
    return {"email": email}


@router.put("/me/emails/primary")
def set_primary(body: Email, person_id: int = Depends(current_person)):
    email = body.email.strip().lower()
    with get_conn() as conn:
        conn.execute("SELECT 1 FROM core.person WHERE person_id = %s FOR NO KEY UPDATE",
                     (person_id,))
        conn.execute("UPDATE core.person_email SET is_primary = false "
                     "WHERE person_id = %s AND is_primary", (person_id,))
        changed = conn.execute(
            "UPDATE core.person_email SET is_primary = true "
            "WHERE person_id = %s AND email = %s", (person_id, email)).rowcount
        if not changed:
            raise HTTPException(404, "Bu e-posta sizin değil.")  # rolls back
    return {"primary": email}


@router.delete("/me/emails")
def remove_email(email: str, person_id: int = Depends(current_person)):
    email = email.strip().lower()
    with get_conn() as conn:
        conn.execute("SELECT 1 FROM core.person WHERE person_id = %s FOR NO KEY UPDATE",
                     (person_id,))
        row = conn.execute("SELECT is_primary FROM core.person_email "
                           "WHERE person_id = %s AND email = %s", (person_id, email)).fetchone()
        if row is None:
            raise HTTPException(404, "Bu e-posta sizin değil.")
        if row[0]:
            raise HTTPException(409, "Birincil e-posta silinemez; önce başka birini birincil yapın.")
        conn.execute("DELETE FROM core.person_email WHERE person_id = %s AND email = %s",
                     (person_id, email))
    return {"removed": email}


# ---- submission ----------------------------------------------------------
class Author(BaseModel):
    email: str = Field(max_length=254)
    full_name: str | None = None  # needed only if the person is not known yet
    share: Decimal = Field(gt=0, le=100, decimal_places=2)
    institution: str | None = None
    corresponding: bool = False


AUTHORS = TypeAdapter(list[Author])


def check_authors(authors: list[Author]):
    for a in authors:
        a.email = clean_email(a.email)
    if not authors:
        raise HTTPException(422, "En az bir yazar gerekli.")
    if sum(a.corresponding for a in authors) != 1:
        raise HTTPException(422, "Tam olarak bir sorumlu yazar işaretleyin.")
    total = sum(a.share for a in authors)
    if total != 100:
        raise HTTPException(422, f"Katkı paylarının toplamı {total}; 100 olmalı.")


def find_person(conn, author: Author) -> int:
    """The existing account with this email; otherwise a new inactive account."""
    row = conn.execute("SELECT person_id FROM core.person_email WHERE email = %s",
                       (author.email,)).fetchone()
    if row:
        return row[0]
    if not (author.full_name or "").strip():
        raise HTTPException(422, f"{author.email} kayıtlı değil: yazarın adını girin.")
    person_id = conn.execute(
        "INSERT INTO core.person (full_name) VALUES (%s) RETURNING person_id",
        (author.full_name.strip(),)).fetchone()[0]
    conn.execute("INSERT INTO core.person_email (email, person_id, is_primary) "
                 "VALUES (%s, %s, true)", (author.email, person_id))
    return person_id


def find_institution(conn, name: str | None) -> int | None:
    name = (name or "").strip()
    if not name:
        return None
    row = conn.execute(
        "SELECT institution_id FROM core.institution WHERE lower(name) = lower(%s) "
        "ORDER BY institution_id LIMIT 1", (name,)).fetchone()
    return row[0] if row else conn.execute(
        "INSERT INTO core.institution (name) VALUES (%s) RETURNING institution_id",
        (name,)).fetchone()[0]


def resolve_authors(conn, authors: list[Author]):
    """[(person_id, author)] in the given order."""
    resolved = [(find_person(conn, a), a) for a in authors]
    if len({p for p, _ in resolved}) != len(resolved):
        raise HTTPException(422, "Aynı kişi iki kez eklenmiş.")
    return resolved


def insert_authors(conn, submission_id, resolved):
    for order, (person_id, a) in enumerate(resolved, start=1):
        conn.execute(
            "INSERT INTO core.authorship (submission_id, person_id, author_order, "
            "contribution_share, institution_id) VALUES (%s, %s, %s, %s, %s)",
            (submission_id, person_id, order, a.share, find_institution(conn, a.institution)))


def set_context(conn, request: Request, person_id: int):
    """Tells the database who is acting and when the request arrived (BR-04)."""
    waited = time.monotonic() - request.state.arrived
    conn.execute(
        "SELECT set_config('app.person_id', %s, true), set_config("
        "'app.request_received_at', (now() - make_interval(secs => %s))::text, true)",
        (str(person_id), waited))


def read_pdf(upload: UploadFile, max_mb: int) -> files.PendingFile:
    limit = max_mb * 1024 * 1024
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"PDF {max_mb} MB sınırından büyük.")
    try:
        return files.PendingFile(files.clean_pdf(data))
    except files.BadPdf as e:
        raise HTTPException(422, str(e)) from e


def max_pdf_mb(conn, track_id: int) -> int:
    row = conn.execute(
        "SELECT p.max_pdf_mb FROM core.track t "
        "JOIN core.conference_policy p ON p.conference_id = t.conference_id "
        "WHERE t.track_id = %s AND p.valid_from <= now() "
        "ORDER BY p.valid_from DESC LIMIT 1", (track_id,)).fetchone()
    return row[0] if row else files.DEFAULT_MAX_MB


def submission_of_key(conn, key, person_id):
    """The submission an earlier try of this request created, if any."""
    row = conn.execute(
        "SELECT s.submission_id, EXISTS (SELECT 1 FROM core.authorship a "
        "  WHERE a.submission_id = s.submission_id AND a.person_id = %s) "
        "FROM core.submission s WHERE s.idempotency_key = %s", (person_id, key)).fetchone()
    if row is None:
        return None
    if not row[1]:
        raise HTTPException(409, "Bu istek anahtarı daha önce kullanılmış.")
    return row[0]


@router.get("/tracks")
def tracks():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT t.track_id, c.name, c.year, t.name, "
            "       core.fn_t1_due_at(t.track_id, 'SUBMISSION'), "
            "       core.fn_t1_submission_open(t.track_id, now()) "
            "FROM core.track t JOIN core.conference c USING (conference_id) "
            "ORDER BY c.year DESC, c.name, t.name").fetchall()
    keys = ("track_id", "conference", "year", "track", "due_at", "open")
    return [dict(zip(keys, r)) for r in rows]


@router.post("/submissions", status_code=201)
def submit(request: Request, response: Response,
           title: str = Form(), abstract: str = Form(), track_id: int = Form(),
           authors: str = Form(description="JSON list of authors"),
           topic_ids: list[int] = Form(default=[]),
           file: UploadFile = File(),
           idempotency_key: uuid.UUID = Header(),
           person_id: int = Depends(current_person)):
    # a retry of a request that already succeeded: same answer, even if it is late now
    with get_conn() as conn:
        done = submission_of_key(conn, idempotency_key, person_id)
        max_mb = max_pdf_mb(conn, track_id)
    if done:
        response.status_code = 200
        return {"submission_id": done, "repeated": True}

    try:
        author_list = AUTHORS.validate_json(authors)
    except ValidationError as e:
        raise HTTPException(422, "Yazar bilgileri geçersiz; payları ve alanları kontrol edin.") from e
    check_authors(author_list)
    if not title.strip() or not abstract.strip():
        raise HTTPException(422, "Başlık ve özet gerekli.")

    pdf = read_pdf(file, max_mb)
    try:
        # BR-06: everything below is one transaction
        with get_conn() as conn:
            set_context(conn, request, person_id)
            # identical requests arriving together are handled one after another
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 1))",
                         (str(idempotency_key),))
            done = submission_of_key(conn, idempotency_key, person_id)
            if done:
                response.status_code = 200
                return {"submission_id": done, "repeated": True}

            resolved = resolve_authors(conn, author_list)
            if person_id not in [p for p, _ in resolved]:
                raise HTTPException(422, "Yazarlardan biri siz olmalısınız.")
            corresponding = next(p for p, a in resolved if a.corresponding)
            submission_id = conn.execute(
                "INSERT INTO core.submission (track_id, title, abstract, idempotency_key, "
                "corresponding_author_id) VALUES (%s, %s, %s, %s, %s) RETURNING submission_id",
                (track_id, title.strip(), abstract.strip(), idempotency_key, corresponding),
            ).fetchone()[0]
            insert_authors(conn, submission_id, resolved)
            conn.execute(
                "INSERT INTO core.submission_version (submission_id, version_no, file_path, "
                "file_hash) VALUES (%s, 1, %s, %s)", (submission_id, pdf.name, pdf.hash))
            if topic_ids:
                # core.submission_topic is created by T3 (004)
                if conn.execute("SELECT to_regclass('core.submission_topic')").fetchone()[0] is None:
                    raise HTTPException(422, "Konu seçimi henüz kullanılamıyor.")
                for topic_id in set(topic_ids):
                    conn.execute("INSERT INTO core.submission_topic (submission_id, topic_id) "
                                 "VALUES (%s, %s)", (submission_id, topic_id))
            pdf.publish()  # the file is in place before the commit
    except psycopg.Error as e:
        pdf.discard(get_conn)
        raise db_error(e) from e
    except BaseException:
        pdf.discard(get_conn)
        raise
    finally:
        pdf.tmp.unlink(missing_ok=True)
    return {"submission_id": submission_id, "repeated": False}


@router.get("/submissions/mine")
def my_submissions(person_id: int = Depends(current_person)):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.submission_id, s.title, s.status, s.created_at, c.name, c.year, t.name,
                   s.corresponding_author_id = %(me)s,
                   (SELECT max(version_no) FROM core.submission_version v
                    WHERE v.submission_id = s.submission_id),
                   (SELECT json_agg(json_build_object(
                               'full_name', p.full_name, 'share', x.contribution_share,
                               'institution', i.name,
                               'corresponding', x.person_id = s.corresponding_author_id)
                               ORDER BY x.author_order)
                    FROM core.authorship x
                    JOIN core.person p ON p.person_id = x.person_id
                    LEFT JOIN core.institution i ON i.institution_id = x.institution_id
                    WHERE x.submission_id = s.submission_id),
                   -- would the database accept a new PDF right now?
                   CASE s.status
                       WHEN 'SUBMITTED' THEN core.fn_t1_submission_open(s.track_id, now())
                       WHEN 'REVISION_REQUESTED' THEN
                           coalesce(now() <= core.fn_t1_due_at(s.track_id, 'REVISION'), false)
                       WHEN 'ACCEPTED' THEN
                           coalesce(now() <= core.fn_t1_due_at(s.track_id, 'CAMERA_READY'), true)
                       ELSE false
                   END
            FROM core.authorship a
            JOIN core.submission s ON s.submission_id = a.submission_id
            JOIN core.track t ON t.track_id = s.track_id
            JOIN core.conference c ON c.conference_id = t.conference_id
            WHERE a.person_id = %(me)s
            ORDER BY s.created_at DESC, s.submission_id DESC
            """, {"me": person_id}).fetchall()
    keys = ("submission_id", "title", "status", "created_at", "conference", "year", "track",
            "is_corresponding", "latest_version", "authors", "can_upload")
    return [dict(zip(keys, r)) for r in rows]


@router.get("/submissions/{submission_id}/versions/{version_no}/file")
def download_version(submission_id: int, version_no: int,
                     person_id: int = Depends(current_person)):
    """The stored PDF, only for the authors of the submission."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT v.file_path FROM core.submission_version v "
            "JOIN core.authorship a ON a.submission_id = v.submission_id AND a.person_id = %s "
            "WHERE v.submission_id = %s AND v.version_no = %s",
            (person_id, submission_id, version_no)).fetchone()
    path = files.storage_dir() / row[0] if row else None
    if path is None or not path.is_file():
        raise HTTPException(404, "Dosya bulunamadı.")
    return FileResponse(path, media_type="application/pdf",
                        filename=f"bildiri-{submission_id}-v{version_no}.pdf",
                        content_disposition_type="inline",
                        headers={"Cache-Control": "private, no-store"})


def own_submission(conn, submission_id, person_id):
    """Locks the submission; only its corresponding author may change it."""
    row = conn.execute(
        "SELECT track_id, status, corresponding_author_id FROM core.submission "
        "WHERE submission_id = %s FOR NO KEY UPDATE", (submission_id,)).fetchone()
    if row is None or row[2] != person_id:
        raise HTTPException(404, "Sorumlu yazarı olduğunuz böyle bir bildiri yok.")
    return row[0], row[1]


# status after the upload that the state machine (Report 2.5) expects
AFTER_UPLOAD = {"REVISION_REQUESTED": "REVISED", "ACCEPTED": "CAMERA_READY"}


@router.post("/submissions/{submission_id}/versions", status_code=201)
def upload_version(submission_id: int, request: Request, response: Response,
                   file: UploadFile = File(), person_id: int = Depends(current_person)):
    with get_conn() as conn:
        track_id, _ = own_submission(conn, submission_id, person_id)
        max_mb = max_pdf_mb(conn, track_id)
    pdf = read_pdf(file, max_mb)
    try:
        with get_conn() as conn:
            set_context(conn, request, person_id)
            _, status = own_submission(conn, submission_id, person_id)
            number, latest_hash = conn.execute(
                "SELECT version_no, file_hash FROM core.submission_version "
                "WHERE submission_id = %s ORDER BY version_no DESC LIMIT 1",
                (submission_id,)).fetchone()
            if pdf.hash == latest_hash:
                if status == "REVISION_REQUESTED":
                    raise HTTPException(422, "Revize sürüm öncekiyle birebir aynı.")
                if status != "ACCEPTED":  # a retry: nothing to add
                    response.status_code = 200
                    return {"version_no": number, "status": status, "repeated": True}
            conn.execute(
                "INSERT INTO core.submission_version (submission_id, version_no, file_path, "
                "file_hash) VALUES (%s, %s, %s, %s)",
                (submission_id, number + 1, pdf.name, pdf.hash))
            new_status = AFTER_UPLOAD.get(status, status)
            if new_status != status:
                conn.execute("UPDATE core.submission SET status = %s WHERE submission_id = %s",
                             (new_status, submission_id))
            pdf.publish()
    except psycopg.Error as e:
        pdf.discard(get_conn)
        raise db_error(e) from e
    except BaseException:
        pdf.discard(get_conn)
        raise
    finally:
        pdf.tmp.unlink(missing_ok=True)
    return {"version_no": number + 1, "status": new_status, "repeated": False}


@router.put("/submissions/{submission_id}/authors")
def change_authors(submission_id: int, authors: list[Author], request: Request,
                   person_id: int = Depends(current_person)):
    check_authors(authors)
    try:
        with get_conn() as conn:
            set_context(conn, request, person_id)
            own_submission(conn, submission_id, person_id)
            locked = conn.execute("SELECT core.fn_t1_authors_locked(%s)",
                                  (submission_id,)).fetchone()[0]
            if locked:
                # let the database record the attempted new list (BR-08)
                conn.execute(
                    "SELECT core.fn_t1_record_attempt(%s, NULL, %s)",
                    (submission_id, Jsonb([a.model_dump(mode="json") for a in authors])))
            else:
                resolved = resolve_authors(conn, authors)
                conn.execute("DELETE FROM core.authorship WHERE submission_id = %s",
                             (submission_id,))
                insert_authors(conn, submission_id, resolved)
                conn.execute(
                    "UPDATE core.submission SET corresponding_author_id = %s "
                    "WHERE submission_id = %s",
                    (next(p for p, a in resolved if a.corresponding), submission_id))
    except psycopg.Error as e:
        raise db_error(e) from e
    if locked:  # raised after the commit, so the record is kept
        raise HTTPException(409, "Yazar listesi kilitli; değişiklik reddedildi.")
    return {"submission_id": submission_id}


@router.post("/submissions/{submission_id}/withdraw")
def withdraw(submission_id: int, request: Request, person_id: int = Depends(current_person)):
    with get_conn() as conn:
        set_context(conn, request, person_id)
        _, status = own_submission(conn, submission_id, person_id)
        # only before the final decision (Report 2.5)
        if status not in ("SUBMITTED", "UNDER_REVIEW", "REVISION_REQUESTED", "WITHDRAWN"):
            raise HTTPException(409, "Karar verilmiş bir bildiri geri çekilemez.")
        if status != "WITHDRAWN":
            conn.execute("UPDATE core.submission SET status = 'WITHDRAWN' "
                         "WHERE submission_id = %s", (submission_id,))
    return {"submission_id": submission_id, "status": "WITHDRAWN"}
