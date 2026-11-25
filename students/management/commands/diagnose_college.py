"""Answer "is this deployment healthy?" in plain language.

    python manage.py diagnose_college ums.gpgaya.ac.in
    python manage.py diagnose_college ums.gpgaya.ac.in --json
    python manage.py diagnose_college            # uses COLLEGE_DOMAIN / ALLOWED_HOSTS

Checks: settings sanity for the domain, database connectivity and migrations, static
files/manifest, e-mail and WhatsApp/SMS configuration, disk space, media and cache,
background jobs and error tracking. Exit code 1 when something is BROKEN (2 when only
warnings), so it can gate a deploy script.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

OK, WARN, BROKEN = 'OK', 'WARN', 'BROKEN'


class Command(BaseCommand):
    help = "Check a college deployment for the usual problems and print a readable report"

    def add_arguments(self, parser):
        parser.add_argument("domain", nargs="?", default="",
                            help="college domain, e.g. ums.gpgaya.ac.in")
        parser.add_argument("--json", action="store_true", dest="as_json",
                            help="machine-readable output")
        parser.add_argument("--skip-network", action="store_true",
                            help="do not test outbound SMTP/Twilio reachability")

    # ── checks ───────────────────────────────────────────────────────────
    def checks(self, domain, skip_network):
        yield from self.check_domain(domain)
        yield from self.check_settings()
        yield from self.check_database()
        yield from self.check_migrations()
        yield from self.check_static()
        yield from self.check_media()
        yield from self.check_cache()
        yield from self.check_email(skip_network)
        yield from self.check_messaging()
        yield from self.check_jobs()
        yield from self.check_disk()
        yield from self.check_backups()

    def check_domain(self, domain):
        hosts = list(getattr(settings, 'ALLOWED_HOSTS', []))
        if domain:
            found = domain in hosts or any(h.startswith('.') and domain.endswith(h) for h in hosts)
            yield ('domain', 'Domain/ALLOWED_HOSTS',
                   OK if found else BROKEN,
                   f'{domain} {"is" if found else "is NOT"} in ALLOWED_HOSTS ({", ".join(hosts) or "empty"})')
            try:
                socket.gethostbyname(domain)
                yield ('dns', 'DNS', OK, f'{domain} resolves')
            except OSError as exc:
                yield ('dns', 'DNS', WARN, f'{domain} does not resolve here ({exc})')
        else:
            yield ('domain', 'Domain/ALLOWED_HOSTS', OK if hosts else BROKEN,
                   f'ALLOWED_HOSTS = {", ".join(hosts) or "empty"}')

    def check_settings(self):
        yield ('debug', 'DEBUG', OK if not settings.DEBUG else BROKEN,
               'DEBUG=False' if not settings.DEBUG else 'DEBUG=True — never ship this')
        secret = settings.SECRET_KEY or ''
        weak = len(secret) < 40 or secret.startswith('django-insecure')
        yield ('secret', 'SECRET_KEY', WARN if weak else OK,
               'looks weak/short' if weak else f'{len(secret)} characters')
        yield ('env', 'ENVIRONMENT', OK, getattr(settings, 'ENVIRONMENT', '(unset)'))
        yield ('secure', 'Cookie/HTTPS flags',
               OK if settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE else WARN,
               f'SESSION_COOKIE_SECURE={settings.SESSION_COOKIE_SECURE}, '
               f'CSRF_COOKIE_SECURE={settings.CSRF_COOKIE_SECURE}')

    def check_database(self):
        from django.db import connection

        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
            size = None
            if connection.vendor == 'postgresql':
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_database_size(current_database())')
                    size = cursor.fetchone()[0] / (1024 * 1024)
            yield ('database', 'Database', OK,
                   f'{connection.vendor} {connection.settings_dict.get("NAME", "")}'
                   + (f' ({size:.1f} MB)' if size else ''))
        except Exception as exc:  # noqa: BLE001
            yield ('database', 'Database', BROKEN, f'cannot connect: {exc}')

    def check_migrations(self):
        try:
            out = subprocess.run(
                [sys.executable, 'manage.py', 'showmigrations', '--plan'],
                cwd=settings.BASE_DIR, capture_output=True, text=True, timeout=120)
            pending = [line.strip() for line in out.stdout.splitlines()
                       if line.strip().startswith('[ ]')]
            if pending:
                yield ('migrations', 'Migrations', BROKEN,
                       f'{len(pending)} not applied (first: {pending[0]})')
            else:
                yield ('migrations', 'Migrations', OK, 'all applied')
        except Exception as exc:  # noqa: BLE001
            yield ('migrations', 'Migrations', WARN, f'could not list migrations: {exc}')

    def check_static(self):
        root = Path(settings.STATIC_ROOT or '')
        manifest = root / 'staticfiles.json'
        if not root.exists():
            yield ('static', 'Static files', BROKEN,
                   f'STATIC_ROOT {root} does not exist — run collectstatic')
            return
        if not manifest.exists():
            yield ('static', 'Static files', BROKEN,
                   f'no manifest at {manifest} — run collectstatic')
            return
        count = sum(1 for _ in root.rglob('*'))
        yield ('static', 'Static files', OK, f'{manifest.stat().st_size // 1024} KB manifest, {count} entries')

    def check_media(self):
        root = Path(settings.MEDIA_ROOT)
        if not root.exists():
            yield ('media', 'Media folder', BROKEN, f'{root} does not exist')
            return
        writable = os.access(root, os.W_OK)
        yield ('media', 'Media folder', OK if writable else BROKEN,
               f'{root} ({"writable" if writable else "NOT writable"})')
        protected = getattr(settings, 'MEDIA_PROTECTED', True)
        yield ('media_protected', 'Media protection', OK if protected else WARN,
               'served through Django with a login check' if protected
               else 'MEDIA_PROTECTED=False — uploaded files are public')

    def check_cache(self):
        from django.core.cache import cache

        try:
            cache.set('diagnose-probe', '1', 5)
            ok = cache.get('diagnose-probe') == '1'
        except Exception as exc:  # noqa: BLE001
            yield ('cache', 'Cache', BROKEN, f'cache unusable: {exc}')
            return
        backend = settings.CACHES['default']['BACKEND'].rsplit('.', 1)[-1]
        note = '' if ok else ' (write not readable back)'
        yield ('cache', 'Cache', OK if ok else BROKEN, f'{backend}{note}')

    def check_email(self, skip_network):
        backend = settings.EMAIL_BACKEND.rsplit('.', 1)[-1]
        console = settings.EMAIL_BACKEND.endswith(('console.EmailBackend', 'locmem.EmailBackend',
                                                   'filebased.EmailBackend'))
        if console and not settings.DEBUG:
            yield ('email', 'E-mail', BROKEN,
                   f'{backend} does not deliver in production — set EMAIL_BACKEND')
            return
        if console:
            yield ('email', 'E-mail', OK, f'{backend} (development: mail is printed)')
            return
        missing = [name for name, value in (
            ('EMAIL_HOST', settings.EMAIL_HOST),
            ('EMAIL_HOST_USER', settings.EMAIL_HOST_USER),
            ('EMAIL_HOST_PASSWORD', settings.EMAIL_HOST_PASSWORD),
        ) if not value]
        yield ('email', 'E-mail', WARN if missing else OK,
               f'{backend} host={settings.EMAIL_HOST}:{settings.EMAIL_PORT}'
               + (f' — missing {", ".join(missing)}' if missing else ''))
        if not skip_network and not missing:
            try:
                from django.core.mail import get_connection

                connection = get_connection(timeout=settings.EMAIL_TIMEOUT)
                connection.open()
                connection.close()
                yield ('email_connect', 'SMTP connection', OK, 'connected and closed cleanly')
            except Exception as exc:  # noqa: BLE001
                yield ('email_connect', 'SMTP connection', BROKEN, f'{exc}')

    def check_messaging(self):
        sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        yield ('whatsapp', 'WhatsApp (Twilio)', OK if sid and token else WARN,
               'keys present' if sid and token else
               'TWILIO_ACCOUNT_SID/AUTH_TOKEN missing — WhatsApp messages are skipped')
        sms = getattr(settings, 'TWILIO_SMS_FROM', '')
        yield ('sms', 'SMS sender', OK if sms else WARN,
               sms or 'TWILIO_SMS_FROM missing — SMS channel disabled')

    def check_jobs(self):
        cluster = getattr(settings, 'Q_CLUSTER', {})
        yield ('queue', 'Job queue', OK,
               f'broker={cluster.get("orm", "-")} workers={cluster.get("workers")} '
               f'sync={cluster.get("sync")}')
        try:
            from django_q.models import Failure, OrmQ

            queued = OrmQ.objects.count()
            failed = Failure.objects.filter(stopped__gte=settings_and_now_minus_day()).count()
            state = OK if queued < 500 and failed < 20 else WARN
            yield ('queue_state', 'Queue state', state,
                   f'{queued} queued, {failed} failed in the last 24h')
        except Exception as exc:  # noqa: BLE001
            yield ('queue_state', 'Queue state', WARN, f'queue tables unavailable: {exc}')

    def check_disk(self):
        usage = shutil.disk_usage(settings.BASE_DIR)
        free_gb = usage.free / (1024 ** 3)
        pct_free = usage.free / usage.total * 100
        if free_gb < 1:
            state = BROKEN
        elif pct_free < 10:
            state = WARN
        else:
            state = OK
        yield ('disk', 'Disk space', state,
               f'{free_gb:.1f} GB free ({pct_free:.0f}%) of {usage.total / (1024 ** 3):.1f} GB')

    def check_backups(self):
        try:
            from students.models import BackupRecord

            newest = BackupRecord.objects.order_by('-created_at').first()
        except Exception as exc:  # noqa: BLE001 - e.g. migrations not applied yet
            yield ('backup', 'Backups', BROKEN, f'cannot read backup records: {exc}')
            return
        if newest is None:
            yield ('backup', 'Backups', WARN,
                   'no backup recorded — run ./scripts/backup_db.sh')
            return
        age_hours = (settings_and_now() - newest.created_at).total_seconds() / 3600
        state = OK if age_hours <= getattr(settings, 'BACKUP_MAX_AGE_HOURS', 48) else WARN
        yield ('backup', 'Backups', state,
               f'last backup {age_hours:.1f}h ago ({newest.size_mb} MB, '
               f'{"encrypted" if newest.encrypted else "PLAINTEXT"})')

    # ── output ───────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        domain = options["domain"].strip()
        results = list(self.checks(domain, options["skip_network"]))
        broken = [r for r in results if r[2] == BROKEN]
        warned = [r for r in results if r[2] == WARN]

        if options["as_json"]:
            self.stdout.write(json.dumps({
                'domain': domain or None,
                'ok': not broken,
                'checks': [{'key': k, 'name': n, 'status': s, 'detail': d}
                           for k, n, s, d in results],
            }, indent=2))
        else:
            self.stdout.write(f"College UMS diagnosis — {domain or settings.COLLEGE_NAME}")
            self.stdout.write(f"environment: {getattr(settings, 'ENVIRONMENT', '?')} | "
                              f"python: {sys.version.split()[0]} | dir: {settings.BASE_DIR}\n")
            for _key, name, status, detail in results:
                colour = {OK: self.style.SUCCESS, WARN: self.style.WARNING,
                          BROKEN: self.style.ERROR}[status]
                self.stdout.write(f"  {colour(status.ljust(6))} {name.ljust(22)} {detail}")
            self.stdout.write('')
            self.stdout.write(
                f"summary: {len(results) - len(broken) - len(warned)} ok, "
                f"{len(warned)} warning(s), {len(broken)} broken")
            if broken:
                self.stdout.write(self.style.ERROR("Fix the BROKEN rows before going live."))
            elif warned:
                self.stdout.write(self.style.WARNING("Warnings are not fatal; review them anyway."))
            else:
                self.stdout.write(self.style.SUCCESS("This deployment looks healthy."))

        if broken:
            raise SystemExit(1)
        if warned:
            raise SystemExit(2)


def settings_and_now():
    from django.utils import timezone

    return timezone.now()


def settings_and_now_minus_day():
    from datetime import timedelta

    return settings_and_now() - timedelta(hours=24)
