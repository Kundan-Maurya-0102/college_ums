# Security — College UMS

Last audit: this session (dev branch). Scope: whole Django project (`college_ums/`, `students/`).
Everything below was re-checked against the code, not assumed.

Reproduce:

```bash
.venv/bin/python manage.py check
DEBUG=False SECRET_KEY="$(.venv/bin/python -c 'from django.core.management.utils import get_random_secret_key as k; print(k())')" \
  ALLOWED_HOSTS=ums.example.edu CSRF_TRUSTED_ORIGINS=https://ums.example.edu \
  .venv/bin/python manage.py check --deploy
.venv/bin/python manage.py test
.venv/bin/bandit -r students college_ums -x "*/migrations/*,*/tests/*"
.venv/bin/pip-audit -r requirements.txt
```

## OWASP Top 10 (2021)

| Risk | Status | Where |
|---|---|---|
| A01 Broken access control | Fixed + tested | Role decorators on all 65 panel views (`students/decorators.py`), object-level owner checks (doubts, replies, fees, certificates), matrix tests `students/tests/test_security.py::PermissionMatrixTests`, doc `docs/PERMISSIONS.md` |
| A02 Cryptographic failures | Fixed | `SECRET_KEY` mandatory, dev key rejected when `DEBUG=False`; session/CSRF cookies `Secure` + `HttpOnly` + `SameSite=Lax` in prod; HSTS 30d; passwords via Django hashers; no secrets in code or git history |
| A03 Injection | No raw SQL | ORM only, no `extra()`/`raw()`; CSV imports validated and wrapped in `transaction.atomic`; CSV cell values escaped by templates |
| A04 Insecure design | Partly addressed | Login lockout (`LOGIN_MAX_ATTEMPTS`/`LOGIN_LOCKOUT_MINUTES`), AI chat rate limit (20 / 5 min), audit trail for fee/marks/attendance/imports/users, `/healthz/` DB-free |
| A05 Security misconfiguration | Fixed | `DEBUG` defaults `False`, `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` from env, `check --deploy` clean, non-root Docker image, WhiteNoise, no directory listing |
| A06 Vulnerable components | Upgraded + monitored | Django 4.2.29 → **4.2.30**; `pip-audit` run (9 advisories left, see below); `requirements-dev.txt` pins `pip-audit`, `bandit` |
| A07 Identification/auth failures | Fixed | Brute-force lockout per username+IP, one-time password links expiring in `PASSWORD_TOKEN_TIMEOUT_HOURS` (48h), session rotation on login, password change invalidates sessions (`update_session_auth_hash`), set-password tokens single use |
| A08 Software/data integrity | Partial | CSV content sniffing (not extension trust), upload allow-lists, `AuditLog` for money/marks/attendance; no signed releases yet |
| A09 Logging/monitoring failures | Fixed | `AuditLog` model + `students/audit.py`, console logging config, optional Sentry via `SENTRY_DSN`, `/healthz/` |
| A10 SSRF | Not applicable | No server-side fetches of user-supplied URLs (AI helper only calls the Gemini endpoint with a fixed base URL) |

## Fixes made in this audit

1. **Login brute-force protection** — `students/security.py` (`login_lockout_remaining`, `register_login_failure`,
   `reset_login_failures`), wired into `students/views_student.py:student_login`. Lockout is per
   `username + IP`; counters live in the Django cache (`LOGIN_MAX_ATTEMPTS=5`, `LOGIN_LOCKOUT_MINUTES=15`).
2. **Security headers middleware** — `students/middleware.py:SecurityHeadersMiddleware` adds
   `Content-Security-Policy` (default-src 'self', `frame-ancestors 'none'`, `object-src 'none'`),
   `Permissions-Policy`, `Cross-Origin-Opener-Policy`, and enforces `X-Frame-Options: DENY` /
   `X-Content-Type-Options: nosniff`. Configurable through `SECURITY_CSP`.
3. **Upload hardening** — `validate_upload()` / `safe_upload_name()` reject executables
   (`.exe .bat .sh .php .js .html .svg .py ...`), wrong extensions, empty and oversize files, and rewrite
   names (path traversal, control chars, RTL override). Applied to banners (also PIL-verified),
   assignments and study material. Per-kind limits: `BANNER_MAX_UPLOAD_MB`, `MATERIAL_MAX_UPLOAD_MB`,
   `CSV_MAX_UPLOAD_MB`.
4. **Audit trail** — new `AuditLog` model (migration `0014_auditlog`), `log_action()` helper that never
   raises into the request. Records fee payments, student edits/deletes, marks, bulk attendance, CSV imports.
5. **AI chat endpoint** — was leaking `str(exception)` with HTTP 500 and had no limit. Now returns generic
   messages, validates JSON, caps prompt at 2000 chars, rate-limited 20/5 min per user+IP.
6. **Spoofable client IP** — `X-Forwarded-For` was trusted unconditionally by visit tracking.
   `students/security.py:client_ip()` honours it only when `TRUST_PROXY_HEADERS=true`.
7. **Optional error tracking** — `SENTRY_DSN` enables Sentry with `send_default_pii=False`; absent key = no-op.
8. **Dependency + static analysis** — Django upgraded to 4.2.30; bandit findings fixed (2 `try/except/pass`
   now log at debug level).
9. **Backups** — `scripts/backup_db.sh` (pg_dump + gzip, retention, non-empty check, restore notes).

## Dependency audit (pip-audit)

```
django 4.2.29 -> 19 advisories   (before)
django 4.2.30 ->  9 advisories   (after upgrade)
```

Remaining 9 advisories have **no 4.2.x fix** — upstream fixed them only in Django 5.2.x / 6.0.x.
They are mostly low-impact for this app (e.g. edge cases in admin/file storage). Recommended next step:
plan a Django 5.2 LTS upgrade on a branch (`django-upgrade`, run tests, check deprecated APIs). Until then
run `pip-audit -r requirements.txt` in CI on every release and keep `4.2.x` patched.

Bandit (`-r students college_ums`, tests/migrations excluded): **0 issues** after the fixes.

## Secrets

- `.env` and `deployments/` are gitignored; no `.env`, key or credential file is tracked.
- Full-history scan for `SECRET_KEY=`, AWS keys, private keys, `rzp_live/test_`, `sk-...` found only
  test fixture passwords (`TestPass!2345` inside `students/tests/`) and `openssl rand` generation in
  `scripts/new_college.sh` — no real secret was ever committed.
- `SECRET_KEY` has no fallback; `django-insecure*` keys abort startup when `DEBUG=False`.

## Residual risks / accepted for now

| Risk | Why it remains | Mitigation |
|---|---|---|
| CSP allows `'unsafe-inline'` for script/style | Several templates still use inline `onclick`/`style` | Migrate to `ui.js` handlers, then switch to nonces (Phase 6.3/7) |
| Uploaded study material is served by Caddy without auth | Files live under `/media/` | Move to a protected view or signed URLs when assignments become graded (Phase 7) |
| No MFA / no password strength meter | Not built yet | Enforce Django validators + optional MFA before selling to large colleges |
| Login lockout is cache-based | Cleared on restart, per-process with locmem | Use Redis (`CACHES`) in production, already documented in `.env.example` |
| `AdminUserForm.save()` forces `is_superuser=True` | Legacy behaviour, every admin gets full powers | Split "office admin" vs "superuser" roles (Phase 7 role work) |
| Logout is a GET link | CSRF-unsafe pattern (logout CSRF is low impact) | Move to POST form in Phase 6.3 |
| Django 4.2 advisories without patch | Needs framework upgrade | See dependency section above |

## Per-deployment checklist

1. Real `SECRET_KEY` (48+ random chars), `DEBUG=False`.
2. `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` = the college's real domain(s) only.
3. `TRUST_PROXY_HEADERS=true` **only** when behind Caddy/nginx; keep `false` otherwise.
4. Redis cache for `CACHES` + `LOGIN_*` counters, `SESSION_ENGINE` unchanged (DB cache fine).
5. TLS with auto-HTTPS (Caddy) — HSTS is already sent in prod.
6. `scripts/backup_db.sh` in cron, restore tested once per semester.
7. `pip-audit -r requirements.txt` and `manage.py check --deploy` in the release pipeline.
8. Optional: `SENTRY_DSN` for error alerts.
