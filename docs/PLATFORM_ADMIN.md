# Platform (super admin) panel

The platform owner (you, the seller) gets a separate area to manage every college:
`https://<platform-domain>/platform/`.

## Who can open it

| Role | Access |
|---|---|
| Django superuser | full access |
| Member of group **Platform Admin** (`PLATFORM_ADMIN_GROUP`) | full access |
| College staff/students | **403** (verified in `platform_admin/tests.py`) |
| Anonymous | redirected to login |

Every write is recorded in the audit log (`students.AuditLog`) with the actor and IP.

```bash
# create a platform agent (not a superuser)
python manage.py shell -c "
from django.contrib.auth.models import User, Group
g,_ = Group.objects.get_or_create(name='Platform Admin')
u = User.objects.create_user('support1', password='...', is_staff=True)
u.groups.add(g)"
```

## What it does

| Screen | URL | Notes |
|---|---|---|
| Overview | `/platform/` | college counts, total students, storage, open tickets, 30-day expiry list |
| Colleges | `/platform/colleges/` | name, slug, domain, plan, status, students/limit, storage, last login, expiry; search + status filter + pagination |
| College detail | `/platform/colleges/<id>/` | edit subscription, **suspend/resume**, **download backup**, usage history, its tickets |
| Plans | `/platform/plans/` | price, student limit, **module feature flags**, how many colleges use it |
| Usage | `/platform/usage/` | per-college students/active users/storage + daily snapshots, CSV export |
| Tickets | `/platform/tickets/` | college-raised tickets, reply, close |
| Metrics API | `POST /platform/metrics/<slug>/` | token-only endpoint a college deployment calls to report students/storage/activity |

Plans seed with `python manage.py seed_plans` (Basic 500 / Pro 2000 / Enterprise 10000
students, with the matching module codes in `platform_admin.models.MODULES`).

## Subscription enforcement (real, not decorative)

Each college deployment sets `COLLEGE_SLUG` in its `.env`.
`platform_admin.middleware.SubscriptionStatusMiddleware` looks that slug up in the platform
table (30 s cache) and, when the college is **suspended** or its
`subscription_expires_on` has passed:

- every non-GET request returns **403 + read-only page** (`templates/read_only.html`),
- GET requests keep working, so students can still see their marks and the college can renew,
- login/logout, set-password, `/admin/`, `/healthz/`, `/privacy/`, `/terms/` and `/platform/`
  stay writable,
- platform admins/superusers are never blocked.

Tests: `test_middleware_blocks_writes_for_suspended_college`,
`test_middleware_lets_reads_through_when_suspended`, `test_expired_subscription_is_read_only`.

## Reminders & metrics

```bash
# e-mail colleges whose subscription expires within N days (dry-run first)
python manage.py send_subscription_reminders            # preview
python manage.py send_subscription_reminders --apply    # queues e-mails (django-q2)

# on the college deployment (cron, hourly): push usage to the platform
COLLEGE_SLUG=gp-tekari PLATFORM_URL=https://platform.example.com \
PLATFORM_METRICS_TOKEN=... python manage.py report_college_metrics

# platform side, one-off
python manage.py seed_plans
```

Reminder cron (platform host):

```cron
0 9 * * * cd /srv/ums-platform && .venv/bin/python manage.py send_subscription_reminders --apply
```

Metric push cron (college host):

```cron
15 * * * * cd /srv/ums && .venv/bin/python manage.py report_college_metrics
```

Required env on the platform: `PLATFORM_METRICS_TOKEN` (shared secret),
`PLATFORM_BACKUP_DIR` (only files inside this directory can be downloaded via the
"Download backup" button — path traversal is impossible, see
`test_backup_path_outside_allowed_dir_is_not_served`). On a college:
`COLLEGE_SLUG`, `PLATFORM_URL`, `PLATFORM_METRICS_TOKEN`.

## Backup download

"Download backup" streams the file at `College.backup_path` **only** when it resolves inside
`PLATFORM_BACKUP_DIR`; otherwise it returns a JSON configuration/metrics snapshot
(`<slug>-snapshot.json`) which is what support needs to rebuild a deployment. Database dumps
themselves are produced by `scripts/backup_db.sh` on the college host — see
`docs/BACKUP_RESTORE.md`.

## Known limits

- The panel reads metrics that colleges *report*; it does not open other colleges'
  databases. That is deliberate: one college = one database, so cross-college data leaks
  are impossible by design.
- Feature flags are stored on the plan and exposed as `College.has_feature(code)`; wiring
  them into individual screens (hide a menu item when the module is off) is the next step
  and is listed in `PROGRESS.md`.
