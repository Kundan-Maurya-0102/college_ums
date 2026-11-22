# College UMS (Django 4.2)

One codebase, one deployment per college: separate domain, database and `.env`.
Nothing college-specific is hardcoded — branding comes from environment variables.

## Key points
- **No plaintext passwords**: students set their own password via a one-time, expiring link.
- **Admin export**: exports set-password links, not passwords.
- **Branding via env**: `COLLEGE_NAME`, `COLLEGE_LOGO`, `PRIMARY_COLOR`, `COLLEGE_EMAIL`,
  `COLLEGE_PHONE` (+ optional address/website/affiliation/established/principal).
- **Hardened defaults**: `SECRET_KEY` required, `DEBUG=False`, strict `ALLOWED_HOSTS`,
  secure cookies and HSTS in production, CSV upload validation.

## Local run (SQLite)
1. `cp .env.example .env` and set `SECRET_KEY`, `COLLEGE_*` (for local dev `DEBUG=True`).
2. `python -m venv .venv && .venv/bin/pip install -r requirements.txt`
3. `.venv/bin/python manage.py migrate`
4. `.venv/bin/python manage.py createsuperuser`
5. `.venv/bin/python manage.py runserver`

## CSV onboarding (secure)
- Upload CSV at **`/admin-panel/upload/`**
- Then export student set-password links from **`/admin-panel/credentials/export-links/`**
- Share each link with the correct student (WhatsApp/SMS/Email).

## Docker (local stack: Postgres + Django)
```bash
cp .env.example .env          # set SECRET_KEY and DB_PASSWORD
docker compose up --build
docker compose exec web python manage.py createsuperuser
# open http://127.0.0.1:8000
```
The container entrypoint runs `migrate` + `collectstatic` and then gunicorn.
Uploaded media lives in the `media` volume.

## Production deployment (Caddy + Postgres + gunicorn)
1. Create the deployment (generates a fresh `.env` with strong secrets, chmod 600):
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
       --env-file deployments/<slug>/.env exec web python manage.py createsuperuser
   ```
4. Open `https://<domain>/login/`.

Caddy terminates TLS automatically, proxies to gunicorn and serves `/media/*` from the
shared `media` volume. Each college gets its own compose project, database and volumes,
so `docker compose -p <slug> ... down` never touches another college.

## Operations
- Liveness probe: `GET /healthz/` (no DB, no auth; exempt from HTTPS redirect for the
  container healthcheck).
- Logs: `docker compose -p <slug> -f docker-compose.prod.yml logs -f web caddy`
- Backup: `docker compose -p <slug> -f docker-compose.prod.yml exec db pg_dump -U <db_user> <db_name> > backup.sql`
  (the generated deployment `README.md` contains the exact commands).

## Environment variables
See `.env.example`. Required in every environment: `SECRET_KEY`. Production also needs
`DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and Postgres `DB_*` values.
