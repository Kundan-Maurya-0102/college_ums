# Claim audit — "Done" ka sach

Din: Phase B (is session). Method: `PROGRESS.md` + `VERIFICATION.md` ki har Done
claim ke liye code khud dekha, phir command/test chalaya. "PROGRESS.md mein likha
hai" ko evidence nahi maana gaya.

Labels:
- **Sach mein** — code hai, aur test/command se chalta hua dikha.
- **Sirf dikhta tha → ab sach** — UI/text tha, kaam nahi karta tha; is session mein fix hua.
- **Pending** — code hi nahi hai. `PROGRESS.md` mein Pending likha gaya hai.

| # | Claim | Status | Evidence (is session) |
|---|---|---|---|
| 1 | Env-driven branding (`COLLEGE_*`), blank = block hidden | **Sach mein** | `college_ums/settings.py:232+`, `students/context_processors.py`, rendered pages carry `COLLEGE_NAME`; `students/tests/test_settings.py` |
| 2 | Security headers, CSP, login lockout, upload allow-list | **Sach mein** | `students/security.py`, `students/middleware.py`, `students/tests/test_security.py` (31) |
| 3 | Audit log for money/marks/attendance | **Sach mein** | `students/audit.py:log_action`, 20 call sites (`views/finance.py` 2, `views/people.py` 8, `views/academics.py` 4, `views/imports.py` 2, `views/reports_feedback.py` 3), `AuditLog` model + migration `0014` |
| 4 | Tests + CI (ruff, bandit, pip-audit, migrations, prod settings) | **Sach mein** | `scripts/ci.sh` OK, `.github/workflows/ci.yml`, **283 tests OK**, ruff 0 |
| 5 | Views package / pagination / indexes / custom 403-404-500 | **Sach mein** | `students/views/` 9 modules, `students/pagination.py`, migrations `0013`–`0017`, `templates/{403,404,500}.html` |
| 6 | Design system + student panel + teacher polish | **Sach mein** | `static/css/theme.css`, `templates/base.html`, `students/tests/test_ux.py` (13), `scripts/ux_audit.py` (110 renders) |
| 7 | Table tools (search, sort, CSV export of view) | **Sach mein** | `static/js/tables.js` client-side on rendered rows; `data-table` markup; no server state |
| 8 | PWA (installable, offline page) | **Sach mein** | `/manifest.webmanifest` view returns per-college JSON with 3 icons (live-checked 200), `/sw.js`, `/offline/`, `students/tests/test_pwa.py` |
| 9 | Charts on dashboard | **Sach mein** | `templates/admin_dashboard/index.html:341` `json_script` of `branch_stats`; `views/dashboard.py:36-39` real `Count()` aggregate; Chart.js vendored locally |
| 10 | Reports page | **Sach mein (read-only analytics)** | `views/dashboard.py:reports_view` real aggregates (branch, <75% defaulters, fee totals, cache). **No PDF/Excel export** — CSV export sirf students/set-password lists par (`views/people.py:205,228`) |
| 11 | Certificates | **Sirf dikhta tha → ab sach (wording)** | Page renders a real printable certificate and `window.print()` works, but the legend said "Download Certificates" — nothing downloads. Legend ab "Print / save as PDF" kehta hai |
| 12 | Fees: online payment / Razorpay | **Pending** | `grep -rEl "razorpay\|RAZORPAY" --include=*.py` → **0 files**. `FeePayment.PAYMENT_MODES` has `ONLINE/UPI` only as *manually recorded* modes. Gateway work needs `RAZORPAY_KEY_ID/SECRET` |
| 13 | E-mail notifications | **Sirf dikhta tha → ab sach** | Pehle `EMAIL_*` settings hi nahi thi → Django default SMTP `localhost:25`, container me har mail fail. Ab: env-driven `EMAIL_BACKEND/HOST/PORT/USER/PASSWORD/TLS`, branded `DEFAULT_FROM_EMAIL`, `manage.py check_email`, 16 tests (`students/tests/test_notifications_real.py`) |
| 14 | WhatsApp notifications | **Sach mein, par credentials ke bina skip** | `students/whatsapp.py`, `tasks.send_whatsapp_task` real Twilio call, retries; without `TWILIO_*` → `skipped (no credentials)` (logged, not faked). `twilio==9.13.0` clean clone me install hota hai |
| 15 | SMS notifications | **Sirf dikhta tha → ab sach** | `notify('sms')` WhatsApp sender se bhejta tha. Ab `send_sms_task` (`TWILIO_SMS_FROM`, plain number, no `whatsapp:` prefix); sender blank = `skipped (no SMS sender)`, downgrade nahi |
| 16 | Background jobs + retries | **Sach mein** | `students/tasks.py:with_retries` (1s/2s/4s), inline fallback, `students/tests/test_tasks.py` (15); retry log live dekha gaya (pichhle round) |
| 17 | Super Admin panel (plans, colleges, usage, tickets, suspend) | **Sach mein** | `platform_admin/` models + views + `platform_admin/tests.py` (32); `/platform/` live 200 |
| 18 | Subscription enforcement (read-only on suspend/expiry) | **Sach mein** | `platform_admin/middleware.py:SubscriptionStatusMiddleware` + tests |
| 19 | Platform metrics API + reminders | **Sach mein** | `report_college_metrics.py` real HTTP POST, `send_subscription_reminders.py` queues via `tasks.notify("email", ...)` (ab deliverable, #13) |
| 20 | Backup/restore | **Sach mein (scripted)** | `scripts/backup_db.sh` + `restore_db.sh`, `docs/BACKUP_RESTORE.md`; Postgres dump path **verify nahi hua** (is machine par pg_dump nahi) — SQLite copy path tested |
| 21 | Media behind login | **Sach mein** | `students/views/media.py:serve_media`, `MEDIA_PROTECTED`, tests in `test_backlog_fixes.py` |
| 22 | AI assistant | **Sach mein (labelled fallback)** | `students/ai_helper.py`: `GEMINI_API_KEY` ho to `google-genai` call, warna `[Offline Mode]` canned answer — user ko saaf dikhta hai ki AI nahi chala |
| 23 | Demo seed + landing + bug report | **Sach mein** | `manage.py seed_demo`, `templates/landing.html`, `students.BugReport`; `students/tests/test_demo_and_feedback.py` (22) |
| 24 | Landing page "screenshots" | **Sirf dikhta hai (CSS mockup)** | `templates/landing.html` uses pure-CSS previews, not real screenshots. Section ab "Illustrative preview" label karta hai — koi jhootha product screenshot nahi |
| 25 | Parent portal, exam PDFs (hall ticket/marksheet), timetable clash detection, admission module, notification bell, global search | **Pending** | `grep` se koi code nahi mila (har term ke liye 0 files except `year_of_admission` field). `PROGRESS.md` → Next section me Pending |
| 26 | Multi-college isolation (tenant tests) | **Adhura → Phase C me** | Design single-tenant-per-DB hai, lekin cross-college leak ka automated proof nahi tha. Phase C me Colleges A/B suite add hui |
| 27 | Load/performance numbers (`36.1 → 210.6 req/s`) | **Ek baar measure hua, dobara verify nahi** | `PERFORMANCE.md` method + `scripts/load_test.py` maujood; is session me load test nahi chalaya (numbers historical) |
| 28 | Docker image build / compose up | **Adhura** | Machine par `docker: command not found`. Static checks + `students/tests/test_docker_context.py` (5) + entrypoint pipeline local simulate kiya (gunicorn + /healthz/ + /readyz/ + static 200) |

## Is audit se nikle asli bugs (fix ho gaye)

1. **Email kabhi deliver nahi hoti thi** — koi `EMAIL_*` config nahi, silent SMTP localhost:25 → ab env-driven + `check_email`.
2. **`sms` channel WhatsApp par jaata tha** → ab alag `send_sms_task`.
3. **`.dockerignore` `*.png`** se PWA icons + apple-touch-icon image se bahar ho jaate the (har page 500 in container) → root-anchored patterns.
4. **`manage.py test` fresh clone me fail** tha (staticfiles manifest) → tests plain storage, setup me `collectstatic`.
5. **`create_college` command hi nahi tha** (README isse maangta tha) → naya command + 14 tests.
6. **Shell scripts `100644`** commit hue the → `./scripts/dev_setup.sh` fresh clone me permission denied → +x.

## Ab bhi khula (imaandaar list)

- Razorpay/UPI collection, parent portal, exam PDFs, timetable clash, admission
  workflow, notification bell, global search — **code nahi hai**.
- Docker/Caddy runtime (docker installed nahi).
- Postgres backup/restore path is machine par verify nahi hua.
- Django 4.2 (9 advisories) → 5.2 LTS.
