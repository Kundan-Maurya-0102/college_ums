# Deployment — staging, production, deploys and rollbacks

One codebase, one deployment per college (own domain, DB, `.env`, volumes).
Staging is just another deployment of the same tag with `ENVIRONMENT=staging`.

## Environments

| Env | `ENVIRONMENT` | DEBUG | HSTS | Sentry | Data |
|---|---|---|---|---|---|
| local | `development` | True | — | off | SQLite, seeded demo data |
| staging | `staging` | False | 1 day, no preload | env `staging` | copy of production data (anonymised) |
| production | `production` | False | 30 days + preload | env `production` | real student data |

Staging uses the same security middleware and settings path as production, so a
template/settings bug shows up there first. Differences are explicit:

```bash
# staging .env
ENVIRONMENT=staging
ALLOWED_HOSTS=staging.ums.example.edu
COLLEGE_NAME=Example Polytechnic (staging)
DATA_RETENTION_YEARS=1     # shorter retention on test data
SENTRY_ENV=staging
```

## First install of a college

```bash
./scripts/new_college.sh gp-tekari \
  --name "Government Polytechnic Tekari" --domain ums.gp-tekari.edu \
  --email office@gp-tekari.edu --phone 0612-1234567

./scripts/deploy.sh gp-tekari          # build + backup + migrate + health check
```

`new_college.sh` writes `deployments/<slug>/.env` (chmod 600), a README with the
exact commands, and the per-college DNS/compose notes.

## Routine deploy

```bash
git pull
./scripts/deploy.sh gp-tekari                     # current HEAD
./scripts/deploy.sh gp-tekari --tag v1.4.2        # a specific tag/ref
./scripts/deploy.sh gp-tekari --dry-run           # show the steps only
```

Order of operations (script enforced): **backup → build → migrate → up →
health check**. If the health check fails 20×3 s, the script prints the last 60
web log lines and rolls back to the tag before the current one.

## Rollback

```bash
./scripts/deploy.sh gp-tekari --rollback      # previous tag from releases/<slug>/tags.txt
./scripts/deploy.sh gp-tekari --tag v1.4.1    # or an explicit older tag
```

Rollback swaps the image tag; **it does not undo migrations**. If the bad release
added a destructive migration, restore the pre-deploy backup
(`docs/RUNBOOK.md` §3) instead.

## Update every college at once

```bash
./scripts/update_all.sh --dry-run          # preview
./scripts/update_all.sh                    # deploy current HEAD everywhere
./scripts/update_all.sh --only gp-tekari,abc-college
```

Each college still gets its own backup, its own health check and its own DB; the
script stops that college on failure and continues with the rest, then prints a
summary and exits non-zero if anything failed. Run it from a clean checkout of
the tag you intend to ship.

## Release procedure (recommended)

1. `./scripts/ci.sh` locally (mirrors GitHub Actions) and push; wait for green CI.
2. Tag: `git tag -a v1.5.0 -m "..." && git push --tags`.
3. Deploy staging: `./scripts/deploy.sh staging --tag v1.5.0`.
4. Smoke staging as admin/teacher/student (`docs/USER_GUIDE.md` quick paths).
5. `./scripts/update_all.sh` (deploys `v1.5.0` to every college) or a single
   `./scripts/deploy.sh <slug> --tag v1.5.0`.
6. Watch `/readyz/`, Sentry and the uptime monitor for 30 minutes.

## What not to do

- Do not `docker compose down -v` — that removes the DB volume.
- Do not edit `.env` on the server and forget to `dc up -d web` (settings are read at start).
- Do not run `migrate` by hand against production before a backup.
- Never commit `deployments/` (git-ignored) — it holds secrets.
