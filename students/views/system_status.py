"""Admin-facing System status page: is this deployment healthy right now?

Everything on the page is measured, not asserted: the database is pinged, the media
directory is walked for its real size, django-q2's own tables report queued/failed
jobs, and the last backup is taken from the recorded rows (falling back to the newest
file in BACKUP_DIR when the script has not recorded one).
"""
import os
import shutil
from datetime import timedelta

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db import connection, connections
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from ..models import BackupRecord, ErrorEvent, StudentProfile


def _dir_size(path, limit_files=20000):
    """Total bytes under `path`; stops early on huge trees rather than hanging."""
    total = files = 0
    for root, _dirs, names in os.walk(path):
        for name in names:
            try:
                total += os.path.getsize(os.path.join(root, name))
                files += 1
            except OSError:
                continue
            if files >= limit_files:
                return total, files, True
    return total, files, False


def _database_status():
    started = timezone.now()
    info = {'engine': connection.vendor, 'name': '', 'size_mb': None, 'latency_ms': None,
            'ok': True, 'error': ''}
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        info['latency_ms'] = round((timezone.now() - started).total_seconds() * 1000, 1)
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute('SELECT current_database(), pg_database_size(current_database())')
                name, size = cursor.fetchone()
                info['name'], info['size_mb'] = name, round(size / (1024 * 1024), 2)
        else:
            info['name'] = str(connection.settings_dict.get('NAME', ''))
            try:
                info['size_mb'] = round(os.path.getsize(info['name']) / (1024 * 1024), 2)
            except OSError:
                info['size_mb'] = None
    except Exception as exc:  # noqa: BLE001 - the page must render even when the DB is sick
        info['ok'] = False
        info['error'] = str(exc)[:200]
    return info


def _job_status():
    """Queue health from django-q2's own tables (missing app = nothing queued)."""
    status = {'available': False, 'queued': 0, 'success_24h': 0, 'failed_24h': 0,
              'last_success': None, 'last_failure': None, 'failures': []}
    try:
        from django_q.models import Failure, OrmQ, Success
    except Exception:  # noqa: BLE001 - django-q2 not installed in this deployment
        return status

    status['available'] = True
    since = timezone.now() - timedelta(hours=24)
    try:
        status['queued'] = OrmQ.objects.count()
        status['success_24h'] = Success.objects.filter(stopped__gte=since).count()
        failed = Failure.objects.filter(stopped__gte=since).order_by('-stopped')
        status['failed_24h'] = failed.count()
        status['last_success'] = Success.objects.order_by('-stopped').values_list(
            'stopped', flat=True).first()
        status['last_failure'] = failed.values_list('stopped', flat=True).first()
        status['failures'] = list(failed.values('func', 'result', 'stopped')[:5])
    except Exception as exc:  # noqa: BLE001
        status['error'] = str(exc)[:200]
    return status


def _backup_status():
    newest = BackupRecord.objects.order_by('-created_at').first()
    backup_dir = getattr(settings, 'BACKUP_DIR', '') or os.path.join(settings.BASE_DIR, 'backups')
    info = {'record': newest, 'dir': backup_dir, 'dir_size_mb': None, 'files': 0,
            'age_hours': None, 'stale': None, 'newest_file': None}
    if os.path.isdir(backup_dir):
        size, files, _truncated = _dir_size(backup_dir)
        info['dir_size_mb'] = round(size / (1024 * 1024), 2)
        info['files'] = files
        newest_path, newest_mtime = None, 0
        for name in os.listdir(backup_dir):
            full = os.path.join(backup_dir, name)
            if os.path.isfile(full) and os.path.getmtime(full) > newest_mtime:
                newest_path, newest_mtime = full, os.path.getmtime(full)
        if newest_path:
            info['newest_file'] = os.path.basename(newest_path)
            info['age_hours'] = round((timezone.now().timestamp() - newest_mtime) / 3600, 1)
    if newest:
        recorded_age = round((timezone.now() - newest.created_at).total_seconds() / 3600, 1)
        info['age_hours'] = recorded_age if info['age_hours'] is None else min(
            info['age_hours'], recorded_age)
    if info['age_hours'] is not None:
        info['stale'] = info['age_hours'] > getattr(settings, 'BACKUP_MAX_AGE_HOURS', 48)
    return info


def _notification_status():
    """Last notification outcomes, from the job queue's own records."""
    try:
        from django_q.models import Failure, Success
    except Exception:  # noqa: BLE001
        return {'available': False}

    def recent(model):
        return list(model.objects.filter(func__icontains='mail')
                    .order_by('-stopped').values('func', 'stopped', 'result')[:5]) or \
               list(model.objects.filter(func__icontains='whatsapp')
                    .order_by('-stopped').values('func', 'stopped', 'result')[:5])

    local_only = settings.EMAIL_BACKEND.endswith(
        ('console.EmailBackend', 'locmem.EmailBackend', 'filebased.EmailBackend'))
    has_credentials = bool(settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD)
    return {
        'available': True,
        'last_success': recent(Success)[:3],
        'last_failure': recent(Failure)[:3],
        'email_backend': settings.EMAIL_BACKEND.rsplit('.', 1)[-1],
        # "configured" means "can actually leave this server", not "has a setting".
        'email_delivers': not local_only,
        'email_configured': (not local_only)
        and (has_credentials or settings.EMAIL_HOST not in ('', 'localhost', '127.0.0.1')),
        'whatsapp_configured': bool(getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                                    and getattr(settings, 'TWILIO_AUTH_TOKEN', '')),
        'sms_configured': bool(getattr(settings, 'TWILIO_SMS_FROM', '')),
    }


def _storage_status():
    media_root = str(settings.MEDIA_ROOT)
    size, files, truncated = _dir_size(media_root)
    usage = shutil.disk_usage(media_root if os.path.isdir(media_root) else settings.BASE_DIR)
    return {
        'media_root': media_root,
        'media_mb': round(size / (1024 * 1024), 2),
        'media_files': files,
        'truncated': truncated,
        'disk_total_gb': round(usage.total / (1024 ** 3), 1),
        'disk_free_gb': round(usage.free / (1024 ** 3), 1),
        'disk_used_pct': round(usage.used / usage.total * 100, 1),
        'disk_low': usage.free / usage.total < 0.10,
    }


@staff_member_required
@require_GET
def system_status(request):
    since = timezone.now() - timedelta(hours=24)
    errors = ErrorEvent.objects.filter(is_resolved=False)
    context = {
        'now': timezone.now(),
        'environment': getattr(settings, 'ENVIRONMENT', ''),
        'debug': settings.DEBUG,
        'version': getattr(settings, 'RELEASE_VERSION', ''),
        'db': _database_status(),
        'jobs': _job_status(),
        'backup': _backup_status(),
        'notifications': _notification_status(),
        'storage': _storage_status(),
        'errors': {
            'open': errors.count(),
            'last_24h': errors.filter(last_seen__gte=since).count(),
            'occurrences_24h': errors.filter(last_seen__gte=since)
            .aggregate(total=Sum('count'))['total'] or 0,
            'recent': list(errors.order_by('-last_seen')[:5]),
        },
        'students': StudentProfile.objects.count(),
        'db_connections': len(connections.all()),
    }
    return render(request, 'admin_dashboard/system_status.html', context)
