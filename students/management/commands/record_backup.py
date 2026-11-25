"""Record a backup file so the admin panel can show when the last one happened.

Called at the end of scripts/backup_db.sh. Safe to run by hand too:

    manage.py record_backup --path backups/ums-20260101-0230.sql.gz.enc
"""
import hashlib
import os

from django.core.management.base import BaseCommand, CommandError

from students.models import BackupRecord


def sha256_of(path, limit=None):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
            if limit and handle.tell() > limit:
                break
    return digest.hexdigest()


class Command(BaseCommand):
    help = "Register a backup file (path, size, checksum) for the status page"

    def add_arguments(self, parser):
        parser.add_argument("--path", required=True)
        parser.add_argument("--kind", default="database",
                            choices=["database", "media", "manual"])
        parser.add_argument("--note", default="")
        parser.add_argument("--unencrypted", action="store_true",
                            help="mark the file as not encrypted")
        parser.add_argument("--no-checksum", action="store_true",
                            help="skip hashing (large dumps: hashing doubles the IO)")

    def handle(self, *args, **options):
        path = options["path"]
        if not os.path.isfile(path):
            raise CommandError(f"no such backup file: {path}")
        size = os.path.getsize(path)
        checksum = "" if options["no_checksum"] else sha256_of(path)
        record = BackupRecord.objects.create(
            path=os.path.abspath(path)[:400], kind=options["kind"], size_bytes=size,
            encrypted=not options["unencrypted"] and path.endswith(".enc"),
            checksum=checksum, note=options["note"][:200])
        self.stdout.write(self.style.SUCCESS(
            f"recorded {record.kind} backup {record.path} ({record.size_mb} MB)"))
