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

## In progress
- (kuch nahi)

## Next (is order mein karna ye hai)
1. views.py ko modules mein todna
2. WhatsApp/SMS alerts
3. Razorpay fee payment
4. Parent portal + reports
5. create_college management command

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
