# Clean-start report

Kya hua: repo ko **naye folder me clone** kiya (`../fresh_check`, sirf committed code),
aur sirf `README.md` follow karke setup chalaya — jaise ek naya developer / naya
deployment karta hai. Jo toota, wo fix kiya. Phir tests, `check --deploy`,
`makemigrations --check`. Uske baad: Done claims ka audit, aur do-college isolation
suite.

Machine: Python 3.14 venv (deploy target 3.12), Django 4.2.30.
Re-run date: is session.

---

## 1. Fresh clone — jo commands chale

```bash
git clone <repo> ../fresh_check && cd ../fresh_check
./scripts/dev_setup.sh
```

`dev_setup.sh` ne ye kiya (sab pass):

| Step | Result |
|---|---|
| venv + `pip install -r requirements.txt` | OK (twilio 9.13.0, google-genai 3.6.1, django-q2 1.10.0) |
| `.env` banana (random `SECRET_KEY`, `DEBUG=True`, `ALLOWED_HOSTS=localhost,127.0.0.1`) | OK |
| `manage.py migrate` | OK, 40+ migrations |
| `seed_plans` | OK (Basic/Pro/Enterprise) |
| `compile_translations` | OK — `hi/LC_MESSAGES/django.po → django.mo` (54 strings), gettext ki zarurat nahi |
| `collectstatic --noinput` | OK — 145 unmodified, 383 post-processed |
| `create_college --name "Demo College" --slug demo-college --admin-username admin` | OK, admin password ek baar print hua |
| `runserver` | OK |

Live smoke (prod-mode gunicorn, `DEBUG=False`, `ENVIRONMENT=production`):

```
/healthz/           200  {"status":"ok","environment":"production"}
/readyz/            200  {"status":"ready","db":true,"cache":true,...}
/login/             200  (X-Forwarded-Proto: https; warna 301 → https)
/manifest.webmanifest 200 with 3 icons, each icon 200
/admin-panel/ /platform/ /help/ /admin/   login ke baad 200
```

## 2. Jo toota tha — aur fix

| # | Problem (fresh clone me) | Kya dikha | Fix |
|---|---|---|---|
| 1 | `.env.example` me inline comment: `LOG_FORMAT=text          # text \| json` | `ImproperlyConfigured: LOG_FORMAT must be 'text' or 'json'` — pehla `migrate` hi fail | comment apni line par; ab test bhi hai (`test_env_example_has_no_inline_comments`) |
| 2 | `.env.example` me `DEBUG=False` default | local par har page `https://` 301 → dev ko lagta hai app toota hai | README + `dev_setup.sh` `DEBUG=True` likhte hain; troubleshooting table me gotcha |
| 3 | `manage.py create_college` **maujood hi nahi tha** (README isse maangta tha) | `Unknown command: 'create_college'` | naya command: plans seed, `College` row, pehla staff admin (superuser sirf `--superuser`), `Platform Admin` group, `metrics_token`, `--dry-run`, `--update`, slug `unique` guard → `platform_admin/tests_create_college.py` (14 tests) |
| 4 | Weak `SECRET_KEY` prod me chal jaata tha | `DEBUG=False` + `django-insecure-...` → app boot | settings guard: `DEBUG=False` par <40 chars / `django-insecure` / known placeholders reject |
| 5 | Shell scripts git me mode `100644` | `./scripts/dev_setup.sh` → *Permission denied* | `git update-index --chmod=+x`; test har `*.sh` ko `100755` verify karta hai |
| 6 | `manage.py test` fresh clone me **fail**: `ValueError: Missing staticfiles manifest entry for 'images/college_logo.jpg'` | manifest build output hai, clone me nahi | tests `StaticFilesStorage` use karte hain (`RUNNING_TESTS`), prod/CI hashed manifest hi chalata hai; `dev_setup.sh` `collectstatic` karta hai |
| 7 | `.dockerignore` me `*.png` | **container me har page 500** + PWA icons gayab (runserver par kabhi nahi dikhta) | patterns root-anchored: `/*.png`, `/*.pdf`, `/*.jpg`, `/test_*.csv`; `students/tests/test_docker_context.py` (5 tests) har `{% static %}` asset ko ignore-patterns se compare karta hai |
| 8 | `entrypoint.sh` order | translations, migrate ke baad | build step pehle: `compile_translations → migrate → collectstatic → gunicorn` (test lock karta hai) |

## 3. Commands ka result (clean clone)

| Command | Result |
|---|---|
| `manage.py test` | **304 tests OK** (~72s) |
| `manage.py check --deploy` (prod env) | `System check identified no issues (0 silenced).` |
| `manage.py makemigrations --check --dry-run` | `No changes detected` (exit 0) |
| `ruff check .` | `All checks passed!` |

Dev env (`DEBUG=True`) par `check --deploy` 4 warnings deta hai — W004/W008/W012/W016
(HSTS, SSL redirect, secure cookies). **Ye expected hai**: `DEBUG=True` par ye
security switches jaan-boojh kar off hote hain; prod env me 0 issues.

## 4. Docker — **Adhura (verify nahi hua)**

`docker: command not found` is machine par. Jo ho saka:

- `Dockerfile`, `docker-compose.yml`, `docker-compose.prod.yml` YAML parse, `bash -n entrypoint.sh`;
- entrypoint ka poora pipeline **locally simulate** kiya (upar table): wahi steps, wahi
  env, `gunicorn` 2 workers, health/ready/static/redirect sab 200;
- `.dockerignore` ko test se lock kiya (bug #7 isi se mila).

Jo verify **nahi** hua: image build, `docker compose up`, container healthcheck,
Caddyfile binary validation. Ye `CLAIM_AUDIT.md` aur `VERIFICATION.md` me
"Adhura" hi likha hai.

---

## 5. Claim audit — "Done" ka sach

Poora table: `CLAIM_AUDIT.md` (28 claims). Teen "sirf dikhta hai" mile:

1. **Email notifications** — `EMAIL_*` settings hi nahi thi → Django default SMTP
   `localhost:25`, container me har mail fail (retries ke baad Failure row).
   Ab: env-driven backend/host/port/user/password/TLS, branded `DEFAULT_FROM_EMAIL`,
   `manage.py check_email <addr> [--dry-run]`, 16 tests.
2. **SMS channel** — `notify('sms')` WhatsApp sender se bhejta tha (`whatsapp:+...`).
   Ab `send_sms_task` (`TWILIO_SMS_FROM`, plain number); sender blank = skipped,
   downgrade nahi.
3. **Certificates page** — "Download Certificates" likha tha, hota print tha.
   Wording ab sach bolti hai; landing page ka CSS mockup bhi
   "illustrative layout, not a screenshot" label karta hai.

Pending (code hi nahi hai, PROGRESS me Pending likha): Razorpay/UPI collection,
parent portal, exam PDFs (hall ticket/marksheet), timetable clash detection, admission
workflow, notification bell, global search, extra roles.

## 6. Do-college isolation

`students/tests/test_isolation.py` — **21 tests**. College B ke liye asli doosra
database (`college_b`, sirf tests me), B ki rows ko **A ke hi primary keys** diye
gaye. Check hua: 20 pages, search, CSV export, media download, notifications, ID swap,
domain boundary, platform metrics token. Sab pass.

**Ek asli leak mila aur fix hua:** `/platform/metrics/<slug>/` ek hi shared token se
har college ki row likh leta tha — College A, B ka `student_count` badal sakta tha.
Ab har college ka apna `metrics_token` (migration `platform_admin/0003`),
constant-time compare, POST check pehle, shared token sirf us college ke liye jo abhi
token-less hai. Detail: `docs/MULTI_COLLEGE_ISOLATION.md`.

## 7. Ab bhi khula

- Docker/Caddy runtime (docker installed nahi).
- Postgres backup/restore path is machine par verify nahi hua (`pg_dump` absent).
- Load-test numbers (`PERFORMANCE.md`) purane hain — dobara measure nahi hue.
- Django 4.2 (9 advisories) → 5.2 LTS.
- Pending features (upar list).

## 8. Naye developer ke liye ab kya kaafi hai

```bash
git clone <repo> && cd <repo>
./scripts/dev_setup.sh          # venv, .env, migrate, plans, translations, static, college+admin
.venv/bin/python manage.py runserver
```

Login page par 200, `/help/` par guide. Kuch bhi galat ho to README ki troubleshooting
table me wahi error likha hai (LOG_FORMAT, DEBUG=False, missing manifest, permission
denied) — aur har row ke liye ek test maujood hai.
