# College UMS (Django 4.2)

One codebase, **one deployment per college**: separate domain, database and `.env`.
Nothing college-specific is hardcoded — branding comes from environment variables.

- **No plaintext passwords**: students set their own password through a one-time,
  expiring link (48 h); the admin exports *links*, never passwords.
- **Per-college isolation by architecture**: each college runs its own deployment with
  its own database, so no query can reach another college's rows.
- **Hardened defaults**: `SECRET_KEY` required and validated, `DEBUG=False` by default,
  strict `ALLOWED_HOSTS`, secure cookies + HSTS in production, upload validation,
  login lockout, audit log of sensitive actions, PII redaction in logs.
- **Bilingual UI**: English / हिन्दी switch; every form shows its errors in words.

---

## 1. Local run (SQLite, 5 commands)

```bash
git clone <repo> && cd <repo>
./scripts/dev_setup.sh            # venv + .env + migrate + plans + first admin
.venv/bin/python manage.py runserver
```

Open <http://127.0.0.1:8000/login/>. The admin username is `admin` and the temporary
password is printed by the script — change it after logging in.

Add the demo college (50 students, 8 teachers, attendance, marks, fees, notices) with
`./scripts/dev_setup.sh --seed-demo`, or later with
`.venv/bin/python manage.py seed_demo --students 50 --teachers 8`.

### Doing it by hand

```bash
cp .env.example .env                                   # 1. config
#   set DEBUG=True for local work, and a real key:
#   python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # 2. deps
.venv/bin/python manage.py migrate                     # 3. database
.venv/bin/python manage.py seed_plans                  # 4. Basic/Pro/Enterprise
.venv/bin/python manage.py compile_translations         # 5. Hindi .mo files
.venv/bin/python manage.py collectstatic --noinput      # 6. static manifest
.venv/bin/python manage.py create_college --name "Demo College" \
    --slug demo-college --admin-username admin          # 7. first college + admin
.venv/bin/python manage.py runserver                    # 8. serve
```

Notes that save time:

- **`DEBUG=False` forces HTTPS and strict hosts.** For local work keep `DEBUG=True`;
  with `DEBUG=False` every page 301s to `https://` by design.
- `.env.example` is production-shaped. `scripts/dev_setup.sh` rewrites `DEBUG`,
  `ALLOWED_HOSTS` and `SECRET_KEY` for you.
- **Inline comments in `.env` become part of the value.** `LOG_FORMAT=text  # json`
  is read as `text  # json` and the app refuses to start — keep comments on their own
  line.
- With `DEBUG=False`, a placeholder or `django-insecure…` `SECRET_KEY` is rejected at
  startup. That is intentional.

### `create_college` — what it does

```bash
.venv/bin/python manage.py create_college --help
```

It seeds the plans if missing, creates/updates the platform `College` row for this
deployment, creates the first staff admin (**not** a superuser unless `--superuser`),
optionally adds it to the `Platform Admin` group, and prints the password once.
Re-running the same slug needs `--update`; `--dry-run` writes nothing.

Useful options: `--plan basic|pro|enterprise`, `--domain ums.college.edu`,
`--students 900`, `--trial-days 30` (`0` = active at once), `--admin-email`.

---

## 2. CSV onboarding (secure)

1. Upload at **`/admin-panel/upload/`** (dry-run first if you like).
2. Export student set-password links from **`/admin-panel/credentials/export-links/`**.
3. Share each link with the correct student (WhatsApp / SMS / email). Links expire in 48 h.

Single student? **`/admin-panel/students/add/`**.

---

## 3. Docker (local stack: Postgres + Django)

```bash
cp .env.example .env                  # set SECRET_KEY and DB_PASSWORD, DEBUG=True
docker compose up --build
docker compose exec web python manage.py create_college \
    --name "Demo College" --slug demo-college --admin-username admin
# open http://127.0.0.1:8000/login/
```

The entrypoint runs `compile_translations`, `migrate`, `collectstatic`, then gunicorn.
Uploaded media lives in the `media` volume and is served **by Django after a login
check** (see §5), not straight off disk.

---

## 4. Production deployment (Caddy + Postgres + gunicorn)

1. Create the deployment (generates `.env` with strong secrets, `chmod 600`):
   ```bash
   ./scripts/new_college.sh --name "College Name" --domain ums.college.edu \
       --email info@college.edu --phone "+91 ..." --color "#1d4ed8" \
       --affiliation "SBTE Bihar" --established 2016
   ```
2. Point DNS `A`/`AAAA` for the domain at the server (ports 80/443 open).
3. Start it:
   ```bash
   docker compose -p <slug> -f docker-compose.prod.yml \
       --env-file deployments/<slug>/.env up -d --build
   docker compose -p <slug> -f docker-compose.prod.yml \
       --env-file deployments/<slug>/.env exec web python manage.py create_college \
       --name "College Name" --slug <slug> --domain ums.college.edu --plan pro
   ```
4. Open `https://<domain>/login/` and check `https://<domain>/readyz/`.

Day-to-day deploys use the wrapper (backup → build → migrate → health check →
automatic rollback on a failed health check):

```bash
./scripts/deploy.sh <slug>              # deploy the current git tag
./scripts/deploy.sh <slug> --rollback   # back to the previous tag (does not undo migrations)
./scripts/update_all.sh                 # every college in deployments/*, one tag
```

Caddy terminates TLS and proxies to gunicorn; each college gets its own compose
project, database and volumes, so `docker compose -p <slug> … down` never touches
another college. Details: `docs/DEPLOYMENT.md`.

---

## 5. Operations

| Need | Command / URL |
|---|---|
| Liveness (no DB, no auth) | `GET /healthz/` |
| Readiness (DB + cache) | `GET /readyz/` |
| Logs | `docker compose -p <slug> -f docker-compose.prod.yml logs -f web caddy` |
| Backup (encrypted) | `COLLEGE_SLUG=<slug> ./scripts/backup_db.sh` |
| Restore | `./scripts/restore_db.sh --file <backup>.sql.gz.enc` |
| Subscription reminders | `python manage.py send_subscription_reminders --apply` |
| Data retention purge | `python manage.py purge_expired_data` (dry run) `--apply` |

- **Media**: `/media/<path>` is served by Django with a login check; `csv_uploads/`
  is staff-only and path traversal is rejected. Set `MEDIA_PROTECTED=False` only when
  object storage with signed URLs does the access control.
- **Logs**: `LOG_FORMAT=json` emits one JSON object per line with PII redaction.
- Runbooks: `docs/RUNBOOK.md` (outage, restore, DNS/TLS), `docs/OPERATIONS.md` (jobs),
  `docs/BACKUP_RESTORE.md`, `docs/DATA_PRIVACY.md`, `docs/PLATFORM_ADMIN.md`.

---

## 6. Tests, lint and pre-flight checks

```bash
.venv/bin/python manage.py test                  # full suite (240+ tests)
.venv/bin/ruff check .                           # lint
.venv/bin/python manage.py check --deploy        # production settings review
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py compile_translations --check
./scripts/ci.sh                                  # everything above, the CI way
```

CI (`.github/workflows/ci.yml`) runs the suite on Python 3.12, the migration check,
ruff + bandit, pip-audit and a `DEBUG=False` production-settings smoke job.

---

## 7. Environment variables

See `.env.example` (grouped and commented). Required everywhere: `SECRET_KEY`.
Production additionally needs `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`,
and Postgres `DB_*` values. Branding: `COLLEGE_NAME`, `COLLEGE_LOGO`,
`PRIMARY_COLOR`, `COLLEGE_EMAIL`, `COLLEGE_PHONE` (+ `COLLEGE_ADDRESS`,
`COLLEGE_WEBSITE`, `COLLEGE_AFFILIATION`, `COLLEGE_ESTABLISHED`,
`COLLEGE_PRINCIPAL_NAME`). Blank optional values simply hide that block.

---

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `LOG_FORMAT must be 'text' or 'json'` | inline comment after the value in `.env` — move it to its own line |
| Every page 301s to `https://` locally | `DEBUG=False`; set `DEBUG=True` for local work |
| `SECRET_KEY is a placeholder/django-generated dev key` | generate a real key (see §1) |
| `ImproperlyConfigured: app_dirs must not be set when loaders is defined` | old code; upgrade — the cached-loader path is covered by CI |
| `Missing staticfiles manifest entry` | `.venv/bin/python manage.py collectstatic --noinput` (production needs the hashed manifest; `manage.py test` does not) |
| Login says "Account locked … minute(s)" | 5 wrong passwords → 15-minute lockout (restart clears it in dev) |
| Hindi text shows as English | run `manage.py compile_translations` (the `.mo` was not built) |
| Media 404 for a student | file is in `csv_uploads/` (staff-only) or the link is invalid |
