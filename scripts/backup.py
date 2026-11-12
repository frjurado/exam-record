"""Back up the database to the private bucket, or get a backup back.

    python scripts/backup.py                      # snapshot -> bucket, prune old ones
    python scripts/backup.py --local FILE.db.gz   # snapshot to a local file only
    python scripts/backup.py --list               # what the bucket holds
    python scripts/backup.py --download KEY FILE  # fetch one backup from the bucket
    python scripts/backup.py --unpack FILE.db.gz NEW.db   # gunzip into a new SQLite file

In production:  fly ssh console -C "python scripts/backup.py"
A nightly GitHub Actions job (.github/workflows/backup.yml) does exactly that.

The output never includes database contents: this runs in a public repository's logs.
Restoring is described in docs/tech/backups.md.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services import backup_service as backups


def main(argv: list[str]) -> int:
    if not argv:
        client, name = backups.bucket()
        with tempfile.TemporaryDirectory() as tmp:
            archive = backups.snapshot(Path(tmp) / backups.backup_name())
            size = archive.stat().st_size
            removed = backups.upload_and_prune(client, name, archive)
        print(f"Stored {backups.PREFIX}{archive.name} ({size} bytes); pruned {len(removed)}.")
        return 0
    if argv[0] == "--local" and len(argv) == 2:
        archive = backups.snapshot(Path(argv[1]))
        print(f"Wrote {archive} ({archive.stat().st_size} bytes).")
        return 0
    if argv == ["--list"]:
        client, name = backups.bucket()
        for item in backups.list_backups(client, name):
            print(f"{item['size']:>10}  {item['key']}")
        return 0
    if argv[0] == "--download" and len(argv) == 3:
        client, name = backups.bucket()
        client.download_file(name, argv[1], argv[2])
        print(f"Downloaded {argv[1]} to {argv[2]}.")
        return 0
    if argv[0] == "--unpack" and len(argv) == 3:
        print(f"Unpacked to {backups.restore_file(Path(argv[1]), Path(argv[2]))}.")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except backups.BackupError as e:
        print(f"Backup failed: {e}")
        sys.exit(1)
