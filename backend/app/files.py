"""PDF checks and storage (BR-09, Report 5.4).

A file is stored under the SHA-256 of its (cleaned) content: <hash>.pdf
"""
import hashlib
import io
import os
import pathlib
import tempfile

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, NameObject

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_MAX_MB = 10


class BadPdf(ValueError):
    pass


def storage_dir() -> pathlib.Path:
    path = pathlib.Path(os.environ.get("STORAGE_DIR") or ROOT / "storage")
    (path / "tmp").mkdir(parents=True, exist_ok=True)
    return path


def _strip(obj, seen):
    """Removes hidden author information from an object and everything below it."""
    if isinstance(obj, IndirectObject):
        if obj.idnum in seen:
            return
        seen.add(obj.idnum)
        obj = obj.get_object()
    if isinstance(obj, DictionaryObject):
        for key in ("/Metadata", "/PieceInfo", "/LastModified"):
            obj.pop(NameObject(key), None)
        annots = obj.get("/Annots")
        if annots is not None:
            kept = ArrayObject()
            for ref in annots.get_object():
                note = ref.get_object()
                if note.get("/Subtype") == "/FileAttachment":
                    continue
                if note.get("/Subtype") != "/Widget":
                    note.pop(NameObject("/T"), None)  # name of the commenter
                kept.append(ref)
            obj[NameObject("/Annots")] = kept
        for key, value in list(obj.items()):
            if key not in ("/Parent", "/P"):
                _strip(value, seen)
    elif isinstance(obj, ArrayObject):
        for value in obj:
            _strip(value, seen)


def clean_pdf(data: bytes) -> bytes:
    """Checks the PDF signature and returns a copy without metadata.
    The same input always gives the same output (needed for BR-07)."""
    if not data.startswith(b"%PDF-"):
        raise BadPdf("Dosya bir PDF değil.")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise BadPdf("Parola korumalı PDF kabul edilmez.")
        if not reader.pages:
            raise BadPdf("PDF dosyasında sayfa yok.")
        seen = set()
        writer = PdfWriter()
        for page in reader.pages:
            _strip(page, seen)
            writer.add_page(page)  # copies only what the page uses
        writer.metadata = None
        out = io.BytesIO()
        writer.write(out)
    except BadPdf:
        raise
    except Exception as e:  # pypdf raises many types for broken files
        raise BadPdf("PDF bozuk, okunamıyor.") from e
    return out.getvalue()


class PendingFile:
    """A cleaned upload waiting in tmp/ until its database rows are written.

    Order (Report 5.4): temporary file -> insert rows -> publish() -> commit;
    discard() if the commit fails.
    """

    def __init__(self, data: bytes):
        self.hash = hashlib.sha256(data).hexdigest()
        self.name = f"{self.hash}.pdf"
        self.final = storage_dir() / self.name
        self.created = False
        fd, tmp = tempfile.mkstemp(dir=storage_dir() / "tmp", suffix=".pdf")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        self.tmp = pathlib.Path(tmp)

    def publish(self):
        try:
            os.link(self.tmp, self.final)  # atomic, never overwrites
            self.created = True
        except FileExistsError:
            pass  # same content is already stored
        self.tmp.unlink()

    def discard(self, conn_factory):
        """Removes what this upload left behind, unless a committed row uses it."""
        self.tmp.unlink(missing_ok=True)
        if self.created:
            with conn_factory() as conn:
                used = conn.execute(
                    "SELECT 1 FROM core.submission_version WHERE file_hash = %s",
                    (self.hash,)).fetchone()
            if not used:
                self.final.unlink(missing_ok=True)
