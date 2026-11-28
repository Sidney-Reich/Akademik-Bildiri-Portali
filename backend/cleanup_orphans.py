"""Deletes stored PDFs that no database row points to (e.g. after a crash).

Run:  python -m backend.cleanup_orphans [--dry-run]
Files younger than one hour are kept: their upload may still be running.
"""
import sys
import time

from .app import db, files

MIN_AGE_SECONDS = 60 * 60


def cleanup(dry_run=False, min_age=MIN_AGE_SECONDS):
    folder = files.storage_dir()
    old = [p for p in [*folder.glob("*.pdf"), *folder.glob("tmp/*.pdf")]
           if time.time() - p.stat().st_mtime >= min_age]
    # read the rows after listing the files
    with db.get_conn() as conn:
        used = {r[0] for r in conn.execute("SELECT file_path FROM core.submission_version")}
    orphans = [p for p in old if p.parent.name == "tmp" or p.name not in used]
    if not dry_run:
        for p in orphans:
            p.unlink(missing_ok=True)
    return orphans


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    found = cleanup(dry_run=dry)
    for p in found:
        print(("would delete " if dry else "deleted ") + str(p))
    print(f"{len(found)} orphan file(s)")
