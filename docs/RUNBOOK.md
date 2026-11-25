# RUNBOOK — College UMS

On-call guide. Each section: **symptom → first checks → fix → verify**.
Times are IST. Keep `deployments/<slug>/.env` handy; most fixes need the compose
project name (`<slug>`) and the env file.

```bash
# shorthand used below
cd /srv/ums
export ENV_FILE=deployments/<slug>/.env
dc() { docker compose -p <slug> -f docker-compose.prod.yml --env-file "$ENV_FILE" "$@"; }
```

---

## 0. Probes — is it really down?

| Probe | Meaning | Healthy response |
|---|---|---|
| `GET /healthz/` | process is alive (no DB) | `200 {"status":"ok","environment":"production"}` |
| `GET /readyz/` | can serve real traffic (DB + cache) | `200 {"status":"ready","db":true,"cache":true}` |
| `GET /readyz/` failing | DB or cache unusable | `503 {"status":"degraded","db":false,...}` |

```bash
curl -fsS https://<domain>/healthz/ ; curl -fsS https://<domain>/readyz/
```

Configure the uptime monitor (UptimeRobot / BetterStack / Healthchecks.io):

- monitor 1: `https://<domain>/healthz/` every 1 min, keyword `"status": "ok"`
- monitor 2: `https://<domain>/readyz/` every 5 min, expect HTTP 200 (this one
  catches "web up but DB dead")
- alert contacts: platform owner e-mail + WhatsApp; Sentry alerts for exceptions

---

## 0.1 Pehle ye do commands (5 minute me 80% cases pata chal jate hain)

```bash
cd /opt/ums/<slug>
.venv/bin/python manage.py diagnose_college <domain>      # exit 0/1/2 = ok/broken/warn
.venv/bin/python manage.py send_error_digest --dry-run     # last 24h ke errors
```

`diagnose_college` ek-ek line me batata hai: DB reachable?, migrations applied?,
static manifest?, e-mail/SMTP keys + real connection?, Twilio keys?, disk free?,
backup kitna purana?. `BROKEN` row = usi ko pehle theek karo.

Admin panel me **System status** (`/admin-panel/system-status/`) live numbers deta hai:
last backup (age + stale flag), storage, queued/failed jobs (24h), error count.
Uptime/alerting ke liye har college ka error digest roz subah 7 baje super admin ko
jata hai (`send_error_digest`), aur usi page par notification channels ki state dikhti hai.

---

## 1. Site is down (5xx, timeout, blank page)

1. `dc ps` — are `web`, `worker`, `db`, `caddy` all `running`?
2. `dc logs --tail 100 web` — look for `OperationalError`, `ImproperlyConfigured`,
   `disallowed host`, `SECRET_KEY`.
3. `curl -i https://<domain>/healthz/` — no response ⇒ Caddy/DNS/TLS (section 4);
   502 ⇒ web container down; 503 ⇒ DB (section 2).
4. `dc restart web` and re-check `/readyz/`.
5. If a deploy caused it: `./scripts/deploy.sh <slug> --rollback` (goes to the
   previous tag in `releases/<slug>/tags.txt`).
6. Still down? Check disk: `df -h` — a full disk breaks SQLite/Postgres and logs.
   `docker system df` and prune old images if needed.

**Verify:** `/healthz/` 200, `/readyz/` 200, log in as a student.

---

## 2. `/readyz/` says `db: false` (database unreachable)

1. `dc logs --tail 50 db` — "too many connections", "no space left on device",
   "database system is starting up", or auth failure.
2. `dc exec db pg_isready -U <DB_USER> -d <DB_NAME>` (Postgres) or check SQLite
   file perms/size if `DB_ENGINE` is sqlite.
3. Wrong password after an `.env` change ⇒ `dc up -d db web` to reload env.
4. Disk full ⇒ free space, then `dc restart db`.
5. If the DB volume is corrupted, restore from backup (section 3).

---

## 2.1 Deploy naya server (disaster ke baad ya naya college)

```bash
./scripts/provision_server.sh <slug> \
    --name "<College name>" --domain <domain> --plan pro \
    --repo /opt/src/college_ums \
    --restore /var/backups/ums/<slug>-YYYYmmdd-HHMM.sql.gz.enc
```

Ek hi command me: tools check → venv → `.env` (naye SECRET_KEY / BACKUP_ENCRYPTION_KEY /
metrics token) → migrate → plans → translations → collectstatic → restore (agar diya) →
college + admin → `diagnose_college`. Exit code = diagnosis ka code (0 ok, 1 broken,
2 warnings). Dobara chalana safe hai (existing `.env` ko chhedta nahi).

Data-only restore (server theek hai, DB nahi) ke liye `scripts/restore_db.sh` — dekho
`docs/BACKUP_RESTORE.md`.

---

## 3. Restore from backup

Backups: `scripts/backup_db.sh` writes encrypted dumps (see `docs/BACKUP_RESTORE.md`).

```bash
# 1. stop writers (web + worker) so nothing writes during the restore
dc stop web worker

# 2. restore (asks for the encryption key from BACKUP_ENCRYPTION_KEY)
./scripts/restore_db.sh <slug> /var/backups/ums/<file>.sql.gz.enc --yes

# 3. start again
dc up -d web worker

# 4. verify
curl -fsS https://<domain>/readyz/
dc exec web python manage.py shell -c \
  "from django.contrib.auth.models import User; print('users:', User.objects.count())"
```

Notes:
- `restore_db.sh` refuses to run without `--yes` and keeps a pre-restore copy.
- Restore into **staging first** and diff counts before touching production.
- Media (banners/materials) is *not* in the DB dump: restore `media/` from your
  file backup at the same time, otherwise pages show broken images.
- After a restore, run `python manage.py purge_expired_data` (dry-run) to check
  retention state.

---

## 4. Domain / SSL problems

| Symptom | Check | Fix |
|---|---|---|
| `NXDOMAIN` / `ERR_NAME_NOT_RESOLVED` | `dig +short <domain>` | create the A/AAAA record at the DNS provider; wait for TTL |
| `ERR_CERT_*` / expired certificate | `echo | openssl s_client -connect <domain>:443 -servername <domain> 2>/dev/null | openssl x509 -noout -dates` | Caddy renews automatically; if stuck: `dc restart caddy` and check `dc logs caddy` for ACME errors |
| ACME failure "no valid A records" | DNS not public yet, or port 80 blocked | open 80/443 in the firewall/security group; ensure the domain points to this host |
| "Too many certificates" (Let's Encrypt limit) | staging domain getting real certs | use the staging directive in `deploy/Caddyfile` (`tls internal` or the staging CA) for non-production hosts |
| `DisallowedHost` in logs | `ALLOWED_HOSTS` missing the domain | add it to `.env`, then `dc up -d web` |
| CSRF 403 on POST after a domain change | origin not trusted | add `https://<domain>` to `CSRF_TRUSTED_ORIGINS`, restart web |
| Mixed content / broken assets behind a proxy | `SECURE_PROXY_SSL_HEADER` | ensure the proxy sends `X-Forwarded-Proto: https` (Caddy does) |

**Verify:** `curl -I https://<domain>/` returns 200 with `strict-transport-security`,
and the padlock shows a valid certificate in the browser.

---

## 5. Login fails for everyone / one user

1. Everyone: `/readyz/` + `dc logs web | grep "LOGIN"` — login lockout after
   repeated failures is per username+IP (`LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`).
   Restart web (locmem) or wait out the window; with Redis, clear the keys.
2. One user: admin panel → student → **Send set-password link** (never share passwords).
3. Superuser locked out: `dc exec web python manage.py createsuperuser` or
   `manage.py changepassword <user>`.
4. Student sees "No student profile is linked" ⇒ their `User` has no
   `StudentProfile`; re-import or fix roles in the admin panel.

---

## 6. E-mails / WhatsApp not going out

1. Jobs are processed by the `worker` service: `dc ps worker`, `dc logs --tail 50 worker`.
2. django-q failures: Django admin → **Django Q → Failures**, or
   `dc exec web python manage.py shell -c "from django_q.models import Failure; print(Failure.objects.count())"`.
3. Credentials: `.env` must have `EMAIL_*` / `TWILIO_*`; missing ones are reported
   as `skipped (no credentials)` and are **not** retried.
   Sabse pehle: `manage.py check_email you@college.edu` — backend, host aur real
   connection dono batata hai (SMTP failure par clear error).`diagnose_college` ka
   `E-mail` row bhi wahi kehta hai. **System status** page par "not configured —
   mail is only printed" ka matlab hai `EMAIL_BACKEND` console par hai.
4. Queue stuck: `dc restart worker`. Pending count:
   `from django_q.models import OrmQ; print(OrmQ.objects.count())`.
5. Nothing blocks the site: jobs run after the response, so a dead SMTP server
   never 500s a page.

---

## 7. Slow site

1. `/readyz/` latency, then `dc stats` for CPU/memory of db/web.
2. Heavy reports/dashboards are cached (`REPORTS_CACHE_SECONDS`,
   `DASHBOARD_CACHE_SECONDS`); a cache with 0 disables them — check `.env`.
3. DB: `dc exec db psql -U <DB_USER> -d <DB_NAME> -c "SELECT pid, now()-query_start AS age, left(query,80) FROM pg_stat_activity WHERE state='active' ORDER BY age DESC LIMIT 5;"`.
4. Raise workers: `GUNICORN_WORKERS` in `.env`, then `dc up -d web`.
5. Full numbers and method: `PERFORMANCE.md`.

---

## 8. Suspend / resume a college (platform panel)

Read-only mode is enforced by `platform_admin.middleware.SubscriptionStatusMiddleware`
(30 s cache):

```bash
# platform host
.venv/bin/python manage.py shell -c "
from platform_admin.models import College
c = College.objects.get(slug='<slug>'); c.suspend(reason='payment overdue'); print(c.status)"
# resume after payment
.venv/bin/python manage.py shell -c "
from platform_admin.models import College
c = College.objects.get(slug='<slug>'); c.resume(); print(c.status, c.is_read_only)"
```

Writes return 403 with the read-only page; reads stay online. To lift it fast,
extend `subscription_expires_on` or `resume()`; changes appear within 30 s.

---

## 9. Data problems (wrong marks, duplicate students)

1. Never edit rows directly in SQL for student data — use the admin panel so the
   audit log stays complete.
2. Duplicate student ⇒ admin panel → student → **Archive/anonymize** flow, or
   fix the `registration_number` in the edit form (unique index protects).
3. Bad CSV import ⇒ Upload history shows the error rows; fix the file and
   re-upload (imports are idempotent by `registration_number`).
4. Suspected data breach ⇒ follow `SECURITY.md` (rotate `SECRET_KEY`, force
   password resets, check `AuditLog`), and export the affected records via the
   student data-export button before any deletion.

---

## 10. Escalation checklist (paste into the ticket)

```
College/slug:
Environment (staging/production):
Symptom + first seen (IST):
/healthz/ and /readyz/ output:
Last deploy tag (releases/<slug>/tags.txt):
dc ps output:
Relevant log lines (web/worker/db/caddy):
Sentry issue link:
Steps already tried:
```
