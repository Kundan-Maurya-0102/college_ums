# Performance — College UMS

Measured on this machine (12 cores, Python 3.14, **SQLite** dev DB, gunicorn 4 workers ×
4 threads). Production runs Postgres, so SQLite write-lock numbers here are a **worst case**.

Reproduce:

```bash
# 1. query counts per page
.venv/bin/python scripts/profile_pages.py

# 2. load test (start the app first)
.venv/bin/gunicorn college_ums.wsgi:application --bind 127.0.0.1:8899 --workers 4 --threads 4 --daemon
.venv/bin/python scripts/load_test.py --url http://127.0.0.1:8899 --users 100 --iterations 3
```

## Before / after

### DB queries per page (profiler, admin user, 15 students / 19 users)

| Page | Before | After |
|---|---|---|
| `/admin-panel/` dashboard | 20 | **14** (30s cache: 0) |
| `/admin-panel/students/` | 11 | **6** |
| `/admin-panel/students/?q=…&branch=…` | 10 | **5** |
| `/admin-panel/marks/` | 12 | **7** |
| `/admin-panel/results/` | 10 | **5** |
| `/admin-panel/attendance/` | 12 | **7** |
| `/admin-panel/take-attendance/` | 10 | **5** |
| `/admin-panel/fee-payments/` | 10 | **5** |
| `/admin-panel/fees/` | 10 | **5** |
| `/admin-panel/notices/` | 11 | **6** |
| `/admin-panel/teachers/` | 12 | **7** |
| `/admin-panel/reports/` | 16 | **17** cold, **6** warm (2 min cache) |
| `/admin-panel/leave-applications/` | 10 | **5** |
| `/admin-panel/upload-history/` | 11 | **6** |

The count drop is not because pages do less: dev-only `SELECT` warmups and repeated
`COUNT`s inside templates were replaced by single queries.

### Load test — 100 virtual users, 3 rounds (1600 requests)

| Metric | Before | After | Change |
|---|---|---|---|
| Throughput | 36.1 req/s | **210.6 req/s** | **5.8×** |
| p50 latency | 1826 ms | **46 ms** | **40×** |
| p95 latency | 6249 ms | **2400 ms** | 2.6× |
| p99 latency | 7773 ms | **3687 ms** | 2.1× |
| Errors | 0 | 0 | — |

Per page after (same run): attendance p50 34 ms, dashboard 36 ms, fees 29 ms, notices 37 ms,
students 71 ms. `login` p50 2807 ms in this run — see note below.

### Load test — 20 users (more realistic login spread)

| Page | p50 | p95 |
|---|---|---|
| login | 457 ms | 838 ms |
| dashboard | 12 ms | 324 ms |
| students | 20 ms | 106 ms |
| attendance / fees / notices | 12–13 ms | 69–190 ms |
| **overall** | **14 ms** | **425 ms** |

### Login note (honest)

100 **simultaneous** logins are CPU-bound on password hashing (bcrypt, 12 rounds) — every
worker pegs one core, so p50 rises to ~2.8 s even though normal pages stay at ~40 ms.
On a staggered login pattern (20 users) it is 457 ms p50. Mitigations already in place:

- password hash = bcrypt (≈4× cheaper than Django's PBKDF2 default); rounds tunable via
  `BCRYPT_ROUNDS` (lower to 10 on a tiny VPS),
- login throttle (`LOGIN_MAX_ATTEMPTS` / `LOGIN_LOCKOUT_MINUTES`) stops login floods,
- add gunicorn workers on bigger boxes; hashing scales with cores.

## What changed

| Change | Why | Where |
|---|---|---|
| `CONN_MAX_AGE=60` | Django default opens a DB connection per request | `settings.DATABASES` |
| SQLite WAL + `timeout=20` | concurrent readers/writers in dev | `students/apps.py` |
| Cached template loader (prod only) | parsing templates on every request | `settings.TEMPLATES` |
| bcrypt hasher (`BCRYPT_ROUNDS`) | cheaper than PBKDF2 at default cost | `students/hashers.py` |
| Visit tracking skips staff, writes only ≥2s dwell | 2 writes/request saved | `students/middleware.py` |
| Dashboard visit metrics in 1 aggregate | was 3 queries, one full-table scan | `students/views/dashboard.py` |
| Dashboard 30 s cache (`DASHBOARD_CACHE_SECONDS`) | repeated stat queries | same |
| Reports 2 min cache (`REPORTS_CACHE_SECONDS`) | heavy aggregates | same |
| Pagination on feedback/admins/fees | unbounded lists | `people.py`, `finance.py`, `leave_feedback.py` |
| Indexes: `feepayment(status,-payment_date)`, `feepayment(payment_date)`, `internalexam(student,subject)`, `internalexam(exam_date)` | list + result queries | migration `0016`, `0017` |
| Query budgets in tests | catch N+1 regressions in CI | `students/tests/test_performance.py` |

## N+1 audit

- Dashboards use grouped `values().annotate()` + `in_bulk()` (no per-student queries).
- List views use `select_related` / `prefetch_related` (students, teachers, marks, doubts).
- Templates never call model methods inside loops that hit the DB
  (`get_attendance_percentage` is only used on single-student pages).
- Guard tests: `QueryBudgetTests` fail if a page exceeds its query budget.

## Remaining bottlenecks / next steps

1. **Postgres in prod** — SQLite serialises writes; production numbers should be better than
   the 20-user run above.
2. **Sessions**: DB-backed sessions add a write per login. Redis session cache
   (`SESSION_ENGINE=cached_db`) is the next easy win for >500 concurrent users.
3. **Background jobs** — notifications/PDF/CSV heavy work should run off-request
   (django-q2 queue is wired in the next step; see `docs/BACKUP_RESTORE.md` for ops).
4. **Static/media** — served by Caddy/WhiteNoise, not Django; not part of these numbers.
5. **Login page** could pre-warm bcrypt in a thread pool if a college expects
   hundreds of logins in the same minute (rare; current numbers are acceptable).
