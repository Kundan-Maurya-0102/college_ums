# Progress

## Done
- Config cleanup: college name/logo/colors/contact ab env se (COLLEGE_NAME, COLLEGE_LOGO,
  PRIMARY_COLOR, COLLEGE_EMAIL, COLLEGE_PHONE + COLLEGE_ADDRESS/WEBSITE/AFFILIATION/
  ESTABLISHED/PRINCIPAL_NAME). Context processor + `templates/partials/college_colors.html`
  aur `college_logo.html` bane; GP Tekari naam/logo/colors code se hatae.
- Security fixes: SECRET_KEY mandatory (no fallback), DEBUG default False,
  ALLOWED_HOSTS + CSRF_TRUSTED_ORIGINS env se, prod me secure cookies, set-password
  token expiry 48h, CSV upload type/size/content validation, seed passwords DEBUG-only.
- Deploy stack: non-root Dockerfile + `entrypoint.sh` (migrate → collectstatic → gunicorn),
  local compose (Postgres, healthcheck, media volume), `docker-compose.prod.yml`
  (web + db + Caddy TLS), `deploy/Caddyfile`, `scripts/new_college.sh` scaffolder,
  `/healthz/` probe, README deploy docs.
- Tests: 37 tests in `students/tests/` (permissions/roles, CSV form + import, set-password
  token expiry/reuse, healthz + visit logging, env branding, settings hardening).
  `python manage.py test` → OK.

- **Phase 5 (refactor)**: `students/views.py` (1366 lines) → `students/views/` package
  (common, dashboard, people, teacher, imports, academics, content, finance,
  leave_feedback) with `__init__` re-exporting all 70 views (URLs unchanged).
  Added `students/pagination.py` + `partials/pagination.html` (filter-preserving)
  on 9 list pages, grouped DB aggregates on dashboards (removed per-student
  attendance N+1), 9 indexes (migration `0013`), custom 403/404/500 pages.
- **Phase 6.1 (design system + shell)**: `static/css/theme.css` tokens (`--primary`
  from env), dark mode, cards/buttons/forms/tables/badges/alerts/toasts/empty
  states, responsive sidebar; rebuilt `base.html` with inline SVG icon sprite,
  role-based nav, topbar search, breadcrumbs, skip link, `aria-current`; new
  `static/js/ui.js` (drawer, theme persistence, double-submit lock, confirms,
  toasts); new login page; Chart.js (vendored in `static/js/vendor/`) doughnut on
  the admin dashboard; `favicon.svg`; aliased 16 CSS variables templates used but
  that were undefined.
- **Phase 6.2 (student panel shell)**: 9 standalone student pages now extend
  `base.html` with a student nav branch — one header/sidebar, mobile drawer,
  shared messages.
- **Tests**: 47 tests total (added pagination tests + a page-smoke suite that
  renders every admin/teacher/student/public GET route).


- **Security audit + OWASP fixes (is session)**: `students/security.py` (login lockout
  per username+IP, `TRUST_PROXY_HEADERS` gated client IP, upload allow-lists +
  `safe_upload_name`, generic rate limiter), `SecurityHeadersMiddleware` (CSP,
  Permissions-Policy, COOP, nosniff, DENY), `AuditLog` model (migration `0014`) +
  `students/audit.py` hooks (fee, marks, attendance, student edit/delete, CSV import),
  AI chat API hardened (400/429/503, prompt cap, rate limit), Django 4.2.29 → **4.2.30**,
  `requirements-dev.txt` (pip-audit, bandit), `scripts/backup_db.sh`, optional
  `SENTRY_DSN`. Docs: `SECURITY.md`, `VERIFICATION.md`, `docs/PERMISSIONS.md`.
  Tests: `students/tests/test_security.py` (31 new) → **78 total, OK**.

- **Phase 6.3 (tables, forms, teacher polish, PWA)**: `static/js/tables.js` (client-side
  search, click-to-sort with `aria-sort`, CSV export of the current view, "x of y rows"
  counter, auto `data-label` for mobile cards) + toolbar/mobile-card CSS in
  `theme.css`; `data-table`/`data-nosort` markup on all admin list tables. Form UX:
  live `aria-invalid`/`.is-invalid` on blur, `.errorlist` styling, spinner + `aria-busy`
  submit lock. Teacher panel: quick-action tiles on dashboard, proper `.empty-state`
  blocks in students/marks/take-attendance/dashboard. PWA: `/sw.js` (root scope
  service worker: network-first navigations with `/offline/` fallback, cache-first
  `/static/`), `/manifest.webmanifest` (per-college name/theme color from env),
  generated PNG icons (192/512/maskable/apple-touch), installable on Android/iOS.
  Tests: `students/tests/test_pwa.py` (7) → **85 total, OK**.

- Privacy (student/parent data): `/privacy/`, `/terms/` (env-branded, retention years
  variable), data minimization (phone optional, `consent_given_at` on first login),
  log/Sentry redaction (`students/privacy.py`, `students/logging_filters.py`),
  admin data export (JSON) + anonymize (audit-logged), retention purge command
  (`purge_expired_data`), encrypted backups (`scripts/backup_db.sh` + tested
  `scripts/restore_db.sh`), `docs/DATA_PRIVACY.md`, `docs/BACKUP_RESTORE.md`.
  Tests: `students/tests/test_privacy.py` (23). Commit `35ff4c3`.
- Performance: CONN_MAX_AGE, SQLite WAL, cached template loader, bcrypt hasher,
  visit-tracking skip, dashboard aggregate + 30s cache, reports 2min cache,
  pagination on feedback/admins/fee-structure, 4 new indexes, `scripts/profile_pages.py`,
  `scripts/load_test.py`, query budgets in `students/tests/test_performance.py`.
  100 users × 1600 req: **36.1 → 210.6 req/s**, p50 **1826 ms → 46 ms**.
  Numbers + method in `PERFORMANCE.md`. Commit `78d74f1`.
- Background jobs: django-q2 (ORM broker, no Redis), `students/tasks.py`
  (email/WhatsApp/credentials with in-job retries 1s/2s/4s, retryable vs permanent),
  inline fallback when the broker is down, `EMAIL_TIMEOUT`/`HTTP_TIMEOUT`,
  CSV-import crash shows an error instead of a 500, worker service in
  `docker-compose.prod.yml`, `docs/OPERATIONS.md`, `students/tests/test_tasks.py` (15).
  Retries proven live against a real worker ("retry 1/3", "retry 2/3"). Commit `3ae7528`.
- Super Admin panel (`platform_admin` app): College/Plan/UsageSnapshot/SupportTicket/
  TicketReply models, `/platform/` overview + colleges + plans (module feature flags) +
  usage (CSV export) + tickets (reply/close), suspend/resume, one-click backup download
  (path-traversal safe), `SubscriptionStatusMiddleware` (suspended/expired =
  read-only, reads still allowed), token-only metrics API + `report_college_metrics`
  and `send_subscription_reminders` commands, `seed_plans`, `docs/PLATFORM_ADMIN.md`,
  `platform_admin/tests.py` (32). Total suite **161 tests OK**.

- **Ops/CI round**: GitHub Actions (test matrix 3.12 + migrations + ruff + bandit +
  pip-audit + DEBUG=False prod-settings job), `pyproject.toml` ruff config, 808 → 0
  lint errors, `requirements-dev.txt`, `scripts/ci.sh` local mirror. Found and fixed a
  real prod bug: cached template loader + APP_DIRS=True raised
  `ImproperlyConfigured` with DEBUG=False (every page 500). django-q2 pinned to 1.10.0
  (1.11.1 needs Django 5.2).
- **Environments/deploy round**: `ENVIRONMENT` (development|staging|production),
  staging HSTS, `students/log_formatter.py` JSON logs (`LOG_FORMAT=json`) with the
  existing redaction filter, `scripts/deploy.sh` (backup → build → migrate → health
  check → auto-rollback, release history per college) and `scripts/update_all.sh`.
- **Observability round**: `/readyz/` (real DB + cache), `/healthz/` with environment,
  sentry-sdk 2.x pinned, `scrub_sentry_event` hardened (message/transaction/culprit/
  logentry/breadcrumbs), `docs/RUNBOOK.md`, `docs/DEPLOYMENT.md`.
- **UX round**: `scripts/ux_audit.py` (110 renders across roles) → 41 forms showed no
  error text (fixed with `partials/form_errors.html`), 43 pages had no `<h1>`,
  fixed multi-column grids given `.grid-2`/`.grid-split`, empty states for events/fees,
  `rel=noopener` on external links, certificates headings demoted; `docs/UX_AUDIT.md`.
- **i18n/a11y round**: Hindi + English (`LANGUAGES`, `LocaleMiddleware`, `/i18n/`
  switch in topbar and on the login page), 53 translated strings, pure-Python
  `compile_translations` (.po → .mo, no gettext on the host, `--check` in CI),
  `/help/` Help Centre with role-aware answers + keyboard shortcuts, first-login
  tour (`static/js/tour.js`, once per browser, Escape, replayable), `/` and Alt+S
  shortcuts, `prefers-reduced-motion`.
- **GTM round**: `manage.py seed_demo` (50 students/8 teachers/attendance/marks/fees/
  notices/timetable, idempotent, `--flush`, refuses in production), public landing
  page at `/` (features, CSS screenshots, pricing from plans, demo-request form →
  `platform_admin.DemoRequest`), floating "Report a problem" button →
  `students.BugReport` + staff triage at `/admin-panel/bug-reports/`.
- **Docs round**: `docs/USER_GUIDE.md`, `ONBOARDING_CHECKLIST.md`,
  `docs/TERMS_SLA_TEMPLATE.md`, plus a real gap fixed while writing the guide —
  single-student "Add student" (`/admin-panel/students/add/`).
- **Backlog round (top 3)**: `BACKLOG.md` + `CHANGELOG.md`. (1) `/media/` no longer
  served off disk by Caddy — Django auth-checks it, `csv_uploads/` staff-only,
  traversal blocked, `MEDIA_PROTECTED` env; (2) `AdminUserForm` no longer forces
  `is_superuser=True` (flag only for superuser callers, removed when not allowed);
  (3) lockout message explains minutes left + set-password path with a live countdown.
  Tests: 244 total, all OK; ruff clean; `makemigrations --check` clean.

- **Clean-start round (fresh clone)**: naye folder me clone karke sirf README follow kiya.
  Gaps fix: `.env.example` inline comment (`LOG_FORMAT`) se startup crash, `DEBUG=False`
  default se local par har page `https://` redirect, `create_college` command missing
  (naya, 14 tests), weak `SECRET_KEY` prod me reject, shell scripts `100644` →
  `100755`, `scripts/dev_setup.sh` naya, README poora rewrite. Clean clone me:
  `manage.py test` **283 OK**, `check --deploy` 0 issues, `makemigrations --check`
  clean, ruff clean. **Docker build/compose verify nahi hua** (docker installed nahi) —
  iske liye `students/tests/test_docker_context.py` + entrypoint pipeline ka local
  simulate (gunicorn, `/healthz/`, `/readyz/`, static 200).
- **Claim audit (`CLAIM_AUDIT.md`)**: PROGRESS/VERIFICATION ki 28 claims code se
  match ki. 3 "sirf dikhta hai" mile aur fix hue: (a) **email delivery config hi nahi
  thi** → env-driven SMTP + `manage.py check_email` + 16 tests, (b) **`sms` channel
  WhatsApp se jaata tha** → alag `send_sms_task` (`TWILIO_SMS_FROM`), (c) certificate
  page "Download" kehta tha jabki print hota hai → wording fix + landing page ka CSS
  mockup ab "illustrative layout, not a screenshot" label karta hai.
  Pending as-is: Razorpay payment, parent portal, exam PDFs, clash detection,
  admission module, notification bell, global search.

- **Isolation round (College A vs B)**: `students/tests/test_isolation.py` (21 tests) —
  College B ka asli doosra DB (`college_b`, sirf tests), B ki rows ko A ke hi primary
  keys, phir A ke 20 pages + search + CSV export + media download + notifications +
  ID swap + domain boundary scan. **Asli leak fix:** platform metrics endpoint ek shared
  token se kisi bhi college ki row likh sakta tha → `College.metrics_token`
  (migration `platform_admin/0003`), constant-time compare. Docs:
  `docs/MULTI_COLLEGE_ISOLATION.md`. Total suite **304 tests**.
- **Clean start (fresh clone)**: `CLEAN_START_REPORT.md` — 8 gaps (`.env` inline comment,
  `DEBUG=False` default, missing `create_college`, weak `SECRET_KEY` guard, non-executable
  scripts, manifest-dependent tests, `.dockerignore` `*.png`, entrypoint order) sab fix +
  tests. Clean clone me: 304 tests OK, `check --deploy` 0 issues, `makemigrations` clean.

- **Release candidate v1.0.0 (`RELEASE_CHECKLIST.md`)**:
  postgres 18 + `DEBUG=False` par poora app chalaya (gunicorn, 3 workers).
  `scripts/rc_flows.py` se **admin / teacher / student / parent / super admin /
  anonymous** — **112/112 checks pass**; naye server par provisioning ke baad 64/64.
  Naye ops features: **System status page**, **error tracking + daily digest**
  (`send_error_digest`), **`diagnose_college <domain>`** (13 checks, exit 0/1/2),
  **`record_backup`**, **`scripts/provision_server.sh`** (ek command me deployment).
  **Parent portal** bana (`GuardianProfile`, `/parent/`, `add_guardian`) — pehle
  Pending tha. RC me mile aur fix hue: metrics API har machine call par 403
  (csrf_exempt missing), `SESSION/CSRF_COOKIE_SECURE` hardcoded, venv Django 6.1.3
  drift (pin 4.2.30), pg_dump missing par khali backup, `DB_ENGINE=postgres` Django ko
  tod deta tha, restore maujood-na-hone par DB nahi banata tha, provision script source
  repo ka `.env` copy kar deta tha, `ALLOWED_HOSTS` loopback chhod deta tha.
  **Backup drill (asli):** backup → `DROP DATABASE` → restore → 11/12 tables ke counts
  identical (12vi row restore ke baad ki nayi error thi). Gate: 353 tests OK,
  `check --deploy` 0 issues, `makemigrations` clean, ruff clean, bandit medium+ 0,
  pip-audit 9 (sab Django 4.2, 5.2 LTS tak ignore). Tag: **v1.0.0**.

- **Student dashboard redesign (one screen)** — naya student shell:
  `templates/student/shell.html` (top navbar: logo+naam env se, Academics/Services/Links
  dropdowns, search, notification bell with unread badge, profile dropdown, dark-mode
  toggle; left sidebar collapsible + mobile drawer) aur `templates/student/dashboard.html`
  (quick-link pills row, password/fee banner, responsive card grid 3/2/1: Announcements,
  My Messages, My Courses with attendance rings, Fees, Pending assignments, Events,
  Upcoming exams, Attendance+result summary — har card me empty state).
  Data `students/dashboard_data.py` me: 9 aggregate queries (koi N+1 nahi), sirf
  `request.user.studentprofile` ki rows. Naya model `DashboardSettings` (card on/off,
  quick links, dark-mode toggle) Django admin me. Models: `StudentProfile.dashboard_seen_at`
  (unread dots), `FeeStructure.due_date` (due/overdue), `Event.venue/start_time/end_time`
  → migration `0021`. CSS `static/css/dashboard.css` sirf maujooda `theme.css` variables
  (college branding same), JS `static/js/dashboard.js` (drawer, dropdowns, theme cookie,
  subject filter). Tests: `students/tests/test_dashboard_redesign.py` (18) — 200 render,
  student A/B aur College A/B isolation (same PKs), khali data par 200, query budget
  (15 subject add karne par +2 se zyada query nahi), hidden cards, gateway ke bina
  "Pay online" nahi, a11y (ek h1, landmarks, aria-current, badge text).

- **Exam module** — `students/pdf.py` (reportlab: college letterhead from `COLLEGE_*`
  env + `PRIMARY_COLOR` table header, logo, footer, QR) aur `students/exams.py`
  (data + access rules). **Hall ticket**: exams list, photo (optional), instructions,
  verification code + QR. **Marksheet**: internal/external, grade, credits, **SGPA/CGPA**
  (credit-weighted grade points), pass/fail, backlog table. **Bulk**: class ka ek ZIP
  (hall tickets ya marksheets, per-student PDF, 500 ka cap). **Verification**:
  `/verify/<code>/` public page (college + kind + date, masked name/reg, **koi marks
  nahi**). **Audit**: har generation/download `AuditLog` + `ExamDocument` row
  (code, issuer, downloads) — models migration `0022`, `StudentProfile.photo` optional.
  Access: student sirf apna (URL me student id nahi), staff sab, teacher sirf apni class;
  galat code par 403 + `exam.download_denied` audit. Tests:
  `students/tests/test_exam_documents.py` (28) — PDF text (pypdf se verify), SGPA math,
  backlog, khali semester, A-student can't open B's document, **College A/B** (doosre DB
  ka code resolve nahi hota, local row doosri DB me nahi jaata), teacher scope, bulk ZIP,
  audit rows. Deps: `reportlab`, `qrcode`, `pypdf` (tests) pinned in requirements.

- **Student dashboard: one-screen redesign, round 2 (shell + cards + real pages)**:
  audit me pata chala project me **Placement aur Library module nahi hai** — isliye wo
  cards nahi bane (jhooth nahi). Dashboard/sidebar jin modules par link karte the
  (Attendance, Marks/Results, Timetable, Notices, Notes/Assignments) unke **student pages
  hi nahi the** — isliye 5 naye read-only pages `students/views/student_pages.py` +
  `templates/student/{attendance,results,timetable,notices,materials}.html`:
  `/attendance/` (subject-wise held/present/%, 75/60 threshold states, recent absences),
  `/results/` (semester-wise SGPA + CGPA, backlog badge, marksheet PDF link),
  `/timetable/` (week grid, aaj highlight), `/notices/` (sirf apni class + general,
  unread flags `dashboard_seen_at` se), `/materials/` (notes + assignments subject-wise,
  due date overdue red). Sab me **student id URL me nahi** (IDOR-safe), empty states.
  **Shell**: navbar global search (`GET /dashboard/?q=` — subject code/name + notice
  title/content, 60 char cap, sirf apne rows), bell `<details>` dropdown (2+2 preview +
  unread count + "View all notices"), profile dropdown me naam/reg no/branch/sem,
  "Emergency contacts" panel (`COLLEGE_PHONE`/`EMAIL`/`WEBSITE` env se, scroll strip ke
  bahar taaki clip na ho), dismissible alert banner (localStorage key per banner text),
  Escape/outside-click se menus band. **Cards**: har card ka footer action (real URL),
  Courses footer me Overall Attendance + CGPA badge, Fees me receipts list +
  "Fee details & receipts", Exams me date sheet + hall ticket, summary me results +
  marksheet. **Real-browser verification** (Chrome via playwright, dev-only
  `requirements-dev.txt`): 1440/900/375 par **overflowX = 0** sab pages par; grid
  3/2/1 columns; contacts/bell panel viewport ke andar. Isi verification ne 4 real bugs
  pakde: (1) band `<details>` ka panel phir bhi paint ho raha tha (author `display: grid`
  UA hiding ko beat karta hai) → `.dash-menu:not([open]) > .dash-menu-panel{display:none}`;
  (2) mobile par navbar search **0px** wide ho gaya tha → ≤620px par apni row;
  (3) base topbar ka avatar block 375px par 11px overflow → phone par hide + title
  ellipsis; (4) contacts panel scroll strip ke andar clip hota tha → strip ke bahar
  + edge-aware align. Tests: `students/tests/test_student_pages.py` (18) — 200 sab pages,
  anonymous → login, own rows only, B ke marks/notices/materials kabhi nahi, khali
  student par empty state, attendance threshold (75/60), search filter + khali search +
  500-char query truncation, **`href="#"` kahin nahi** + har footer link reverse()
  se match, unread flag logic. Total: **417 tests OK**, `ruff` clean.


- **Student UI QA (all student pages, three widths)**: link crawl (21 pages, 35 links,
  0 broken) + real-Chrome sweep at **360/768/1280** (63 combos) + WCAG contrast maths.
  Final: **overflowX 0 sab par, koi JS error nahi, light+dark me text/badges >= 4.5:1**.
  Asli bugs jo mile aur fix hue (`STUDENT_UI_REPORT.md` me poori table):
  purana `static/css/style.css` (hardcoded hex, Tahoma, 3D borders) har page par
  theme.css ke baad load ho raha tha — delete; uske jaane par pata chala theme.css me
  `box-sizing` hi nahi tha → sab pages padding bhar overflow; ~30 class naam
  (`.muted`, `.small`, `.page-title`, `.mt-24`, `.field`, `.plain-list`, `.stat-*`,
  `.pagination*`, `.fieldset-student` …) bina kisi CSS ke use ho rahe the → ek jagah
  define; fee/leave badges `success/warning/danger` class bana rahe the jo exist nahi
  karte (1.3:1 contrast) → asli `badge-green/yellow/red`; dark mode ke **do switch**
  (`data-theme` aur `.dash-dark` with duplicate hex palette) → ek switch; dark me badges
  light-mode foreground par 2.9:1 → dark tokens lighter; dark me active sidebar
  dark-on-dark → `--ink` on `--primary-100` (15.4:1); `.muted` 4.34:1 → 5.66:1;
  bug-report dialog (har page par 9 inline style), certificate/ID card (18 inline,
  hardcoded `#000`, undefined `var(--highlight)`), forum ke 6 templates (Bootstrap
  classes, `background:#fff` jo dark me safed card, inline `onclick`/`onmouseover`) —
  sab design system par; 4 money/exam/event tables phone par bahar nikal rahe the →
  `.table-responsive` + `min-width:0`. Perf: naya
  `test_student_pages.py::StudentPageQueryBudgetTests` (13 subjects par bhi query
  count +2 se zyada nahi). **418 tests OK**, ruff clean.

## In progress
- Kuch nahi. Dashboard ka Step 2 (shell) + cards + 5 real student pages done.
  Agla: notifications pilot (provider abstraction + dry-run) ya admission module.


## Verification (is session)
- Har Done phase code + tests se verify kiya: `VERIFICATION.md` (20 rows).
  Sach mein done: 15, Adhura: deploy (docker non-installed), onboarding, docs,
  multi-tenant tests. Missing: 6.3, Phase 7 features.
- Naye gaps bhi band kiye: proxy IP spoofing, login lockout, CSP, upload types,
  chat API error leak, audit trail, backup script, Django patch.


## UI/UX Enhancements (completed)
- Modernized student panel with fresh color scheme using PRIMARY_COLOR env variable
- Improved typography using system fonts (Segoe UI / Noto Sans) with better hierarchy
- Enhanced card-based layouts with shadows, rounded corners, and smoother interactions
- Improved tables with hover effects, striped rows, and status badges
- Modern button styles with hover transitions and focus-visible outlines
- Better form styling with consistent input borders, focus rings, and error handling
- Enhanced profile display with summary pills and improved data presentation
- Improved statistics grid with better visual design
- News marquee and banner carousel with improved aesthetics
- Certificate pages with professional design and print optimization
- Responsive design improvements for mobile devices (max-width: 768px breakpoints)
- Micro-interactions: card hover effects, button transitions, focus states
- All 37 existing tests pass with enhanced templates

## Next (is order mein karna ye hai)
1. **Pending features — code hi nahi hai** (claim audit: `CLAIM_AUDIT.md`, rows 12/25):
   online fee payment (Razorpay/UPI gateway), parent portal, exam PDFs
   (hall ticket / marksheet), timetable clash detection, admission workflow,
   notification bell, global search, roles/groups (Principal/HOD/Accountant/Exam Cell).
   Ye "Done" nahi hain aur aage bhi tab tak nahi honge jab tak keys + scope na aaye.
   **Blocked:** `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` (payment), `TWILIO_*`
   (WhatsApp/SMS live send), `GEMINI_API_KEY` (AI answers).
2. Phase 9: feature-flag menu hiding (`College.has_feature()` ko base.html nav me),
   Django 4.2 → 5.2 LTS, Docker/Caddy runtime verification (docker installed nahi).
3. Load-test numbers (`PERFORMANCE.md`) dobara measure karna — abhi purane numbers hain.

## Notes / decisions
- Branding sirf env se: `college_ums/settings.py` (COLLEGE_* + PRIMARY_COLOR) →
  `students/context_processors.py` → templates. Templates me koi college string nahi.
- `COLLEGE_LOGO` static path (`images/x.png`) ya full `https://` URL dono le sakta hai;
  blank = 🎓 icon fallback. `templates/partials/college_logo.html` handle karta hai.
- `PRIMARY_COLOR` `:root { --highlight, --table-header }` override karta hai
  (`templates/partials/college_colors.html`, har template me style.css ke baad include).
- Contact/website/affiliation/established/principal blank chhodne par template us block ko
  hide kar deta hai (koi dummy content nahi dikhta).
- SECRET_KEY: env na ho to startup par `ImproperlyConfigured`; `DEBUG=False` + key
  `django-insecure...` se shuru ho to bhi refuse. Local `.env` me abhi ek dev key hai,
  isliye `DEBUG=False` par app boot nahi karega — deployment se pehle naya key generate karo
  (`python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"`).
- ALLOWED_HOSTS ab strict hai: ad-hoc `django.test.Client()` ko `HTTP_HOST='localhost'`
  chahiye (test runner khud `testserver` add karta hai).
- CSV upload: `CSV_MAX_UPLOAD_MB` (default 5) + `.csv` extension + binary/UTF-8/csv.Sniffer
  check (`students/forms.py:CSVUploadForm.clean_file`).
- Set-password links: `PASSWORD_TOKEN_TIMEOUT_HOURS` (default 48) → `PASSWORD_RESET_TIMEOUT`.
- `generate_data.py` sirf `DEBUG=True` + `SEED_STUDENT_PASSWORD` set hone par chalta hai.
- Deploy model: ek college = ek compose project (`docker compose -p <slug> ...`), apna
  `.env`, apna DB + volumes. `scripts/new_college.sh` `deployments/<slug>/.env`
  (chmod 600) + README banata hai; `deployments/` gitignored aur dockerignored.
- prod compose `.env` `--env-file` se aata hai (`ENV_FILE` interpolation). Caddy `/media/*`
  khud serve karta hai kyunki DEBUG=False par Django media nahi deta.
- `/healthz/` DB-free hai, `WebsiteVisitMiddleware` ise log nahi karta, aur prod me
  `SECURE_REDIRECT_EXEMPT` se HTTP par rehta hai (container healthcheck ke liye).
- ⚠️ Is machine par docker/caddy installed nahi, isliye image build, `compose up` aur
  Caddy config validate nahi hue — sirf YAML parse, `bash -n`, scaffold test, `check` chalaye.
- `.env.example` poora documented hai; `render.yaml` + `docker-compose.yml` me bhi keys hain
  (compose ab SECRET_KEY shell/.env se leta hai, hardcoded "change-me" hata diya).
- Tests: `students/tests.py` hata kar `students/tests/` package bana (auth/permissions,
  csv_upload, password_links, ops, settings). Server par `python manage.py test`.
- ⚠️ Is machine ka venv **Python 3.14** hai jabki Django 4.2 max 3.12 support karta hai;
  Django 4.2 ka test template-instrumentation `BaseContext.__copy__` 3.14 par crash karta
  tha. Isliye `students/tests/__init__.py` me chhota shim hai (deployment image 3.12 hai,
  wahan behavior same). CI/server par Python 3.12 use karna behtar hai.

- Static assets: `collectstatic` chalana zaroori hai (ManifestStaticFilesStorage);
  tests naye static file par fail ho sakte hain agar manifest update na ho.
- Icons inline SVG sprite (`templates/partials/icons.html`) — koi CDN/font dependency
  nahi. Chart.js `static/js/vendor/chart.umd.min.js` me vendored hai (offline safe).
- Page smoke test (`students/tests/test_smoke_pages.py`) har role ke har GET route
  ko render karta hai — naya view todne par turant pakda jayega.
- Template `{% load %}` `{% extends %}` ke baad hi aayega (Django rule).
