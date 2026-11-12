"""Copies of the SQLite database: a consistent snapshot, and its storage in a private bucket.

The snapshot uses SQLite's online backup, which is safe while the app is serving. The
bucket is S3-compatible (Tigris on Fly); `fly storage create` sets the environment
variables read here. A backup contains users' emails, so it must only ever go to private
storage or to an admin's own machine.
"""

import gzip
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings

PREFIX = "backups/"
# How many backups stay in the bucket. One a night makes this about three months.
KEEP = 90


class BackupError(Exception):
    """A backup could not be made or stored. The message is safe to show."""


def database_path() -> Path:
    url = settings.DATABASE_URL
    if not url.startswith("sqlite") or ":///" not in url:
        raise BackupError("Only SQLite databases can be backed up.")
    path = url.split(":///", 1)[1]
    if not path or path == ":memory:":
        raise BackupError("The database is not a file.")
    return Path(path)


def backup_name(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"exam_record-{now:%Y%m%d-%H%M%S}.db.gz"


def snapshot(dest: Path, source: Path | None = None) -> Path:
    """Write a gzipped, integrity-checked copy of the database to `dest`."""
    source = source or database_path()
    if not source.exists():
        raise BackupError(f"Database file not found: {source}")
    with tempfile.TemporaryDirectory() as tmp:
        plain = Path(tmp) / "copy.db"
        src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        dst = sqlite3.connect(plain)
        try:
            src.backup(dst)
            result = dst.execute("PRAGMA integrity_check").fetchone()
        finally:
            dst.close()
            src.close()
        if result is None or result[0] != "ok":
            raise BackupError("The copy failed SQLite's integrity check.")
        with open(plain, "rb") as fin, gzip.open(dest, "wb") as fout:
            shutil.copyfileobj(fin, fout)
    return dest


def restore_file(archive: Path, dest: Path) -> Path:
    """Unpack a backup into a plain SQLite file (never over an existing file)."""
    if dest.exists():
        raise BackupError(f"{dest} already exists; choose another name.")
    with gzip.open(archive, "rb") as fin, open(dest, "wb") as fout:
        shutil.copyfileobj(fin, fout)
    return dest


def bucket() -> tuple[Any, str]:
    """An S3 client and the bucket name, from the variables `fly storage create` sets."""
    name = os.environ.get("BUCKET_NAME")
    endpoint = os.environ.get("AWS_ENDPOINT_URL_S3")
    if not name or not endpoint or not os.environ.get("AWS_ACCESS_KEY_ID"):
        raise BackupError(
            "No backup bucket configured (BUCKET_NAME, AWS_ENDPOINT_URL_S3, AWS_ACCESS_KEY_ID)."
        )
    # Imported here: only the backup script needs it, not the web workers.
    import boto3  # type: ignore[import-untyped]

    client = boto3.client("s3", endpoint_url=endpoint, region_name=os.environ.get("AWS_REGION"))
    return client, name


def list_backups(client: Any, bucket_name: str) -> list[dict[str, Any]]:
    """Stored backups, newest first, as {"key", "size"}. Names sort by date."""
    found: list[dict[str, Any]] = []
    token: str | None = None
    while True:
        kwargs: dict[str, Any] = {"Bucket": bucket_name, "Prefix": PREFIX}
        if token:
            kwargs["ContinuationToken"] = token
        page = client.list_objects_v2(**kwargs)
        found += [{"key": o["Key"], "size": o["Size"]} for o in page.get("Contents", [])]
        token = page.get("NextContinuationToken")
        if not token:
            break
    return sorted(found, key=lambda item: item["key"], reverse=True)


def upload_and_prune(client: Any, bucket_name: str, archive: Path, keep: int = KEEP) -> list[str]:
    """Store `archive` and delete all but the newest `keep`. Returns the deleted keys."""
    client.upload_file(str(archive), bucket_name, PREFIX + archive.name)
    old = [item["key"] for item in list_backups(client, bucket_name)[keep:]]
    for key in old:
        client.delete_object(Bucket=bucket_name, Key=key)
    return old
