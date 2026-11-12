# Backups

The SQLite database on the Fly volume is the project's only real asset. A backup contains
users' email addresses, so it is only ever stored in a private bucket or on an admin's
own machine — never in this (public) repository or its workflow artifacts.

## What happens by itself

- Every night at 03:17 UTC, `.github/workflows/backup.yml` wakes the machine and runs
  `python /app/scripts/backup.py` on it.
- The script takes a consistent snapshot (SQLite online backup, safe while the app runs),
  checks its integrity, gzips it and uploads it to the bucket as
  `backups/exam_record-YYYYMMDD-HHMMSS.db.gz` (UTC).
- The newest 90 are kept; older ones are deleted.
- A failed run shows as a failed workflow in GitHub, which notifies the repository owner.
- GitHub switches scheduled workflows off after 60 days without any commit to a public
  repository, and sends a warning first. Re-enable it from the Actions tab if that happens.

Fly's own daily volume snapshots (kept 5 days by default) remain as a second line.

## One-time setup

```bash
fly storage create --app exam-record-beta --name exam-record-backups
```

This creates a private Tigris bucket and sets `BUCKET_NAME`, `AWS_ENDPOINT_URL_S3`,
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_REGION` as secrets on the app.
Then run the workflow once by hand (Actions → Nightly backup → Run workflow) and check
that it succeeds.

## By hand

- **From the admin page:** "Descargar copia" downloads a snapshot to your computer. Do
  this before a large cleanup.
- **To the bucket, now:** `fly ssh console -C "python /app/scripts/backup.py"`
- **See what is stored:** `fly ssh console -C "python /app/scripts/backup.py --list"`

## Restoring

Restoring replaces the live database, so the site must be stopped while the file is
swapped. Everything contributed after the backup was taken is lost.

1. On the machine, fetch and unpack the backup next to the live file:

   ```bash
   fly ssh console
   python /app/scripts/backup.py --list
   python /app/scripts/backup.py --download backups/exam_record-YYYYMMDD-HHMMSS.db.gz /data/restore.db.gz
   python /app/scripts/backup.py --unpack /data/restore.db.gz /data/restore.db
   ```

2. Still on the machine, keep the current file and swap:

   ```bash
   mv /data/exam_record.db /data/exam_record.before-restore.db
   mv /data/restore.db /data/exam_record.db
   rm -f /data/exam_record.db-wal /data/exam_record.db-shm /data/restore.db.gz
   exit
   ```

3. Restart so every worker opens the restored file (migrations run at boot and bring an
   older backup up to the current schema):

   ```bash
   fly apps restart exam-record-beta
   ```

4. Check the site, then delete `/data/exam_record.before-restore.db`.

To look inside a backup without touching production, download it from the admin page (or
with `--download` and `fly ssh sftp get`), unpack it with `--unpack`, and point a local
`DATABASE_URL` at the result.
