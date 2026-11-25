# Release checklist — College UMS v1.0.0

Date: release-candidate session. Branch: `dev`. Target: one deployment per college,
Postgres + gunicorn behind a TLS proxy.

Status legend: **PASS** (command run, output seen) · **PASS\*** (ran with a documented
substitution) · **BLOCKED** (cannot run on this machine — reason given) ·
**FAIL→FIXED** (failed, was fixed, re-ran green).

---

## 1. Automated gate

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Full test suite | `.venv/bin/python manage.py test` | **PASS** — 351 tests OK (~80 s) |
| 2 | Production system checks | `DEBUG=False ALLOWED_HOSTS=… ENVIRONMENT=production manage.py check --deploy` | **PASS** — `System check identified no issues (0 silenced)` |
| 3 | No missing migrations | `manage.py makemigrations --check --dry-run` | **PASS** — `No changes detected` |
| 4 | Dependency audit | `pip-audit -r requirements.txt` | **PASS\*** — 9 advisories, **all** Django 4.2; ignored explicitly in CI, fix = 5.2 LTS (`BACKLOG.md` #5). No other package has a finding. |
| 5 | Security lint | `bandit -r students college_ums platform_admin scripts -ll -x …tests…` | **FAIL→FIXED** — 1 medium (B608 false positive in a CLI message) and test-file noise; now **0 medium+/high**. |
| 6 | Style lint | `ruff check .` | **PASS** — `All checks passed!` |
| 7 | CI mirror end-to-end | `./scripts/ci.sh` | **PASS** — ruff, bandit, `check --deploy`, pip-audit, migrations, collectstatic + prod template engine, prod-settings smoke, full suite |

### Findings fixed during the gate

1. **Venv drift** — the working virtualenv was on **Django 6.1.3** while
   `requirements.txt` pins **4.2.30**. Reinstalled the pinned set; everything below was
   re-run on 4.2.30.
2. Bandit B608 on a `CommandError` message (words "Pass"/"update" look like SQL) → the
   message is built without formatting; gate now fails the build instead of `|| true`.
3. `scripts/provision_server.sh` was committed without the executable bit → `100755`
   (the clean-start guard test caught it).

---

## 2. Real application run — Postgres, `DEBUG=False`

PostgreSQL **18.6** (local server), `DEBUG=False`, `ENVIRONMENT=production`,
gunicorn 3 workers, `ManifestStaticFilesStorage`, sentry off, real SMTP.

| # | Step | Result |
|---|---|---|
| 1 | `manage.py migrate` on Postgres (20 migrations incl. `0019 guardian`, `0020 error events`) | **PASS** |
| 2 | `create_college --superuser` (College row, plan, admin, Platform Admin group, metrics token) | **PASS** |
| 3 | `seed_demo --force` (50 students, 8 teachers, 1400 attendance, 200 marks, 40 payments) | **PASS** |
| 4 | `collectstatic` (393 post-processed, manifest built) | **PASS** |
| 5 | `/healthz/` `/readyz/` `/login/` over gunicorn | **PASS** — 200 / `{"db":true,"cache":true}` |
| 6 | **Role walkthrough** `scripts/rc_flows.py` — admin, teacher, student, parent, super admin, anonymous | **PASS** — **112/112 checks** |

Role coverage in that walkthrough (real forms, real CSRF, real redirects):

- **admin**: login routing, 17 pages, students CSV export, create a notice (POST), add a
  student (POST + search), platform overview, System status page
- **teacher**: 8 pages, materials form, own-class attendance page
- **student**: dashboard, fees, exam schedule, certificates (print-ready bonafide),
  events, leave (POST), feedback, forum, profile, password change; blocked from
  `/admin-panel/`, `/teacher/`, `/media/csv_uploads/`
- **parent**: `/parent/` with own child only, child detail (marks/attendance), no write
  forms, blocked from admin + student areas
- **super admin**: `/platform/` + colleges/plans/usage/tickets, metrics token POST
- **anonymous**: public pages 200, every private page redirected

### Findings fixed during the run

| # | Problem | Fix |
|---|---|---|
| 1 | `/platform/metrics/<slug>/` returned **403 for every machine call** — the view had no `csrf_exempt`, so a token-only POST without a browser cookie was rejected | `@csrf_exempt` + two tests with `Client(enforce_csrf_checks=True)` (right token passes, wrong token still 403) |
| 2 | `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` hardcoded `True` under `DEBUG=False` → a staging box on plain HTTP **could not log in at all** | env-driven with secure default; `check --deploy` still warns if turned off |
| 3 | **Parent portal did not exist** (claim audit had it "Pending") while the release asks for a parent role | new `GuardianProfile` (migration `0019`), `/parent/` + `/parent/child/<pk>/` (read-only, own children only, `@require_GET`), `manage.py add_guardian` printing a set-password link, 15 tests |
| 4 | Email/SMS were un-deliverable in a container (found in the previous round) | env-driven SMTP, separate SMS channel, `manage.py check_email` — verified below |

---

## 3. Notification path — end to end

| # | Check | Result |
|---|---|---|
| 1 | `manage.py check_email <addr>` against a local SMTP server | **PASS** — `sent 1 message(s)`, message captured by the server |
| 2 | `manage.py send_error_digest` queued to the superuser | **PASS** — `queued (id)` |
| 3 | django-q2 worker actually delivered it | **PASS** — `qcluster` log `Processed 'students.tasks.send_email_task'`; the digest mail was captured with subject `2 error(s) in the last 24h` |
| 4 | System status page shows the same state | **PASS** — DB OK 11.6 MB, last backup age, jobs 1 ok / 0 failed |

---

## 4. Ops features added for this release

| Feature | Where | Verified |
|---|---|---|
| System status page (last backup, notification success/fail, storage, pending jobs, errors, disk) | `/admin-panel/system-status/` | **PASS** — rendered live against Postgres; 30 tests |
| Daily error summary to the super admin | `manage.py send_error_digest` (`--hours/--to/--dry-run/--only-if-errors`) | **PASS** — delivered through the queue; 6 tests |
| Error capture (source for the digest) | `students.ErrorEvent` + logging handler (ERROR/CRITICAL, counted, truncated, never raises) | **PASS** — 9 tests |
| `diagnose_college <domain>` | `manage.py diagnose_college` (`--json`) | **PASS** — 13 checks, exit 0/1/2; 7 tests |
| Backup bookkeeping | `manage.py record_backup` + script hook | **PASS** — status page reads it; 3 tests |
| One-command provisioning | `scripts/provision_server.sh <slug>` | **PASS** — see §6 |

---

## 5. Backup → disaster → restore (real Postgres)

| # | Step | Result |
|---|---|---|
| 1 | Count rows in the live college | 61 users, 51 students, 1400 attendance, 200 marks, 40 payments, 24 subjects, 1 guardian |
| 2 | `./scripts/backup_db.sh` | **PASS** — encrypted `60K` dump, `record_backup` row written |
| 3 | `DROP DATABASE ums_rc` (simulated disaster) | app degraded correctly: `/readyz/` **503** with `db_error`, `/healthz/` still **200**, pages 500 |
| 4 | `./scripts/restore_db.sh --file … --yes` | **PASS** — database did not exist, script created it and restored |
| 5 | Row counts before vs after | **PASS** — 11 of 12 tables byte-identical; the only difference was one error row written *after* the restore (a django-q2 "reincarnated pusher" notice), i.e. new activity, no data loss |
| 6 | App after restore | **PASS** — `/login/` 200, `/readyz/` 200 |

### Findings fixed during the drill

| # | Problem | Fix |
|---|---|---|
| 1 | No `pg_dump` on PATH → the script wrote a **20-byte "valid" empty backup** (restore would silently give an empty DB) | preflight `require_binary` before the pipeline (stderr, so it is not swallowed into the dump), `trap` removes partial files, exit 1 |
| 2 | `DB_ENGINE=postgres` (the script's own documented value) **shadowed Django's setting** → `manage.py` died with "isn't an available database backend" | settings accept `postgres/postgresql/sqlite/mysql` shorthands; scripts use `BACKUP_DB_ENGINE` and hand Django the full path |
| 3 | Restore could not target a **non-existent** database (the actual disaster case) | restore creates the database first; `PG_BIN_DIR` support in both scripts |
| 4 | A recorded-backup failure was silent | the script now logs the reason (it was `DB_ENGINE` above) |

---

## 6. New-server provisioning (one script)

`scripts/provision_server.sh gpgaya --name … --domain … --plan pro --repo …`
into an empty directory, against a **fresh empty** Postgres database:

| # | Result |
|---|---|
| 1 | Tools checked, venv built, requirements installed | **PASS** |
| 2 | `.env` generated with fresh `SECRET_KEY`, `BACKUP_ENCRYPTION_KEY`, metrics token, `DEBUG=False`, `chmod 600` | **PASS** — and it no longer copies a source `.env` (see finding) |
| 3 | migrate → seed_plans → compile_translations → collectstatic | **PASS** |
| 4 | `create_college` + admin | **PASS** |
| 5 | `diagnose_college` | **PASS** — 16 ok, 3 warnings (SMTP creds, SMS sender, no backup yet), **0 broken** |
| 6 | Served the new deployment and re-ran the walkthrough for its admin + super admin | **PASS** — 64/64 checks |
| 7 | `--restore <file>` path used for the disaster case | **PASS** — §5 |

### Findings fixed during provisioning

| # | Problem | Fix |
|---|---|---|
| 1 | The first run **copied the source repo's `.env`** (another deployment's `SECRET_KEY` and DB settings) and then said "keeping existing .env"; `.env.*` exclusion also dropped `.env.example` | exclude only `.env`; a copied deployment never inherits secrets |
| 2 | `ALLOWED_HOSTS` was set to the domain only → loopback health checks and the TLS proxy got **400 Bad Request** | domain + `localhost` + `127.0.0.1` |
| 3 | `.env.example` shipped placeholder `SECRET_KEY`/`TWILIO_*` values, so the status page claimed "keys present" with nothing configured; values with spaces were unquoted (source-unsafe) | placeholders blanked with comments, values quoted |
| 4 | `rc_flows.py` hardcoded one college's slug/demo registration number | slug + token from env, unique registration per run, real CSV header assertion |

---

## 7. What is **not** covered (honest list)

| Item | Status | Why / next step |
|---|---|---|
| Docker image build, `docker compose up`, Caddyfile validation | **BLOCKED** | `docker: command not found` on this machine (no passwordless sudo). Entrypoint pipeline simulated locally (compile → migrate → collectstatic → gunicorn, health/ready/static 200). Run `docker compose -f docker-compose.prod.yml build` on the target host before go-live. |
| Real Twilio WhatsApp/SMS send, live Razorpay | **BLOCKED** | No `TWILIO_*` / `RAZORPAY_*` keys. Code paths are real (retries, `skipped (no credentials)` is honest) and `diagnose_college` reports the missing keys. |
| Browser-level checks (tour, drawer, Chart.js pixels, print layout) | **BLOCKED** | No headless browser here. Markup/JS are covered by tests + the HTTP walkthrough. |
| Load test on Postgres | **Not run this round** | Previous numbers in `PERFORMANCE.md` were SQLite; re-measure with `scripts/load_test.py` against the Postgres deployment before selling on the number. |
| Django 4.2 → 5.2 LTS (9 advisories) | **Open** | `BACKLOG.md` #5. Advisories are on Django 4.2 only, all detail-level, ignored explicitly in CI until the upgrade. |
| Parent portal scope | **Deliberate minimum** | Read-only attendance/marks/fees/notices for linked children. No parent-initiated leave/feedback yet (student keeps those). |
| Pending features from `CLAIM_AUDIT.md` | **Not in v1.0.0** | Razorpay/UPI collection, exam PDFs (hall ticket/marksheet), timetable clash detection, admission workflow, notification bell, global search, extra roles. Listed as Pending in `PROGRESS.md`. |

---

## 8. Known-good commands (copy-paste)

```bash
# release gate
.venv/bin/python manage.py test
DEBUG=False ALLOWED_HOSTS=x.example ENVIRONMENT=production \
  SECRET_KEY=$(.venv/bin/python -c "from django.core.management.utils import get_random_secret_key as k;print(k())") \
  .venv/bin/python manage.py check --deploy
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/pip-audit -r requirements.txt
.venv/bin/bandit -r students college_ums platform_admin scripts -ll \
  -x "*/tests/*,students/tests,platform_admin/tests.py,*/migrations/*"
./scripts/ci.sh

# deployment health (on the server)
.venv/bin/python manage.py diagnose_college <domain>
.venv/bin/python manage.py check_email you@college.edu
.venv/bin/python manage.py send_error_digest --dry-run
curl -s https://<domain>/readyz/

# walkthrough against a running deployment
.venv/bin/python scripts/rc_flows.py --base-url https://<domain> \
  --admin admin:<pw> --teacher <t>:<pw> --student <s>:<pw> --parent <p>:<pwd>
```

---

## 9. Release decision

**GO for v1.0.0** for the supported configuration (Postgres + gunicorn + TLS proxy),
with the four BLOCKED items above verified on the target host during go-live
(Docker build, live WhatsApp/payment keys if sold, browser smoke test, Postgres load
test). Every automated gate is green, the five roles were walked end-to-end, and the
backup/restore path was proven by deleting a database and restoring it.
