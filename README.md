# College UMS (Scalable, production-ready Django)

## What changed (important)
- **No plaintext passwords**: students now set their password via a secure one-time link.
- **Admin export**: exports **set-password links**, not passwords.
- **Production-ready settings**: WhiteNoise for static, Postgres-ready env vars, security headers when `DEBUG=False`.

## Local run (SQLite)
1. Create `.env` (copy `.env.example` and edit):
2. Install:
   - `pip install -r requirements.txt`
3. Migrate:
   - `python manage.py migrate`
4. Create admin:
   - `python manage.py createsuperuser`
5. Run:
   - `python manage.py runserver`

## CSV onboarding (secure)
- Upload CSV from **`/admin-panel/upload/`**
- Then export student set-password links:
  - **`/admin-panel/credentials/export-links/`**
- Share each link with the correct student (WhatsApp/SMS/Email).

## Docker + Postgres (scalable)
1. Start:
   - `docker compose up --build`
2. In another terminal:
   - `docker compose exec web python manage.py migrate`
   - `docker compose exec web python manage.py createsuperuser`
3. Open:
   - `http://127.0.0.1:8000`

## Environment variables
See `.env.example` plus optional DB vars:
- `DB_ENGINE` (default sqlite)
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`

