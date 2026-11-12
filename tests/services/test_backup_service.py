import gzip
import sqlite3
from datetime import datetime, timezone

import pytest

from app.core.config import settings
from app.services import backup_service as backups


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "live.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE users (email TEXT)")
    con.execute("INSERT INTO users VALUES ('someone@test.com')")
    con.commit()
    con.close()
    return path


class FakeBucket:
    def __init__(self, keys=()):
        self.objects = dict.fromkeys(keys, 1)

    def upload_file(self, filename, bucket, key):
        self.objects[key] = 1

    def list_objects_v2(self, **kwargs):
        # Two pages, to exercise the continuation token.
        keys = sorted(k for k in self.objects if k.startswith(kwargs["Prefix"]))
        half = len(keys) // 2
        if "ContinuationToken" not in kwargs and half:
            page = {"Contents": keys[:half], "NextContinuationToken": "more"}
        else:
            page = {"Contents": keys[half:] if half else keys}
        return {**page, "Contents": [{"Key": k, "Size": 1} for k in page["Contents"]]}

    def delete_object(self, Bucket, Key):
        del self.objects[Key]


def test_snapshot_round_trip(source, tmp_path):
    archive = backups.snapshot(tmp_path / backups.backup_name(), source)
    with gzip.open(archive, "rb") as f:
        assert f.read(15) == b"SQLite format 3"

    restored = backups.restore_file(archive, tmp_path / "restored.db")
    con = sqlite3.connect(restored)
    assert con.execute("SELECT email FROM users").fetchall() == [("someone@test.com",)]
    con.close()

    # Unpacking never overwrites an existing file.
    with pytest.raises(backups.BackupError):
        backups.restore_file(archive, restored)


def test_snapshot_of_a_missing_database_fails_clearly(tmp_path):
    with pytest.raises(backups.BackupError):
        backups.snapshot(tmp_path / "out.db.gz", tmp_path / "nope.db")


def test_names_sort_by_date():
    early = backups.backup_name(datetime(2026, 11, 12, 3, 17, 0, tzinfo=timezone.utc))
    late = backups.backup_name(datetime(2026, 12, 1, 3, 17, 0, tzinfo=timezone.utc))
    assert early == "exam_record-20261112-031700.db.gz"
    assert early < late


def test_upload_keeps_only_the_newest(source, tmp_path):
    old = [f"backups/exam_record-202611{day:02d}-031700.db.gz" for day in range(1, 6)]
    client = FakeBucket([*old, "other/untouched.txt"])
    archive = backups.snapshot(tmp_path / "exam_record-20261112-031700.db.gz", source)

    removed = backups.upload_and_prune(client, "bucket", archive, keep=3)

    assert removed == sorted(old[:3], reverse=True)
    assert sorted(client.objects) == [
        "backups/exam_record-20261104-031700.db.gz",
        "backups/exam_record-20261105-031700.db.gz",
        "backups/exam_record-20261112-031700.db.gz",
        "other/untouched.txt",
    ]


def test_database_path(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:////data/exam_record.db")
    assert backups.database_path().as_posix() == "/data/exam_record.db"
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    with pytest.raises(backups.BackupError):
        backups.database_path()
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://x/y")
    with pytest.raises(backups.BackupError):
        backups.database_path()


def test_no_bucket_configured(monkeypatch):
    monkeypatch.delenv("BUCKET_NAME", raising=False)
    with pytest.raises(backups.BackupError):
        backups.bucket()
