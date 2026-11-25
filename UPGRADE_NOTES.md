# Upgrade notes — Django 4.2 → 5.2 LTS

Branch: `django52`. Reason: 9 security advisories on 4.2 had no 4.2 fix (only 5.2/6.x),
so `pip-audit` needed an ignore list. Django 4.2 left mainstream support in April 2026;
5.2 is the current LTS.

## What changed

| File | Change | Why |
|---|---|---|
| `requirements.txt` | `Django==4.2.30` → **`Django==5.2.19`** | current 5.2 LTS patch |
| `requirements.txt` | `django-q2==1.10.0` → **`1.11.1`** | 1.11.x requires Django ≥ 5.2; the old pin existed only because 4.2 could not run it |
| `requirements.txt` | `sentry-sdk>=2.19,<3.0` → **`>=2.76,<3.0`** | `send_default_pii` is deprecated in 2.7x; the replacement option exists from there |
| `college_ums/settings.py` | Sentry `send_default_pii=False` → **`data_collection={"user_info": False, "cookies": False, "request_body": False, "query_string": False}`** | same privacy guarantee (nothing about a student leaves the deployment) without the deprecation |
| `students/forms.py` | `StudyMaterialForm.external_link` declared explicitly with `assume_scheme="https"` | Django 6.0 changes the `URLField` default to https; declaring it now removes the warning and gives teachers the https behaviour immediately |
| `students/tests/test_observability.py` | same Sentry option | keeps the wiring test honest |
| `scripts/ci.sh`, `.github/workflows/ci.yml` | **`--ignore-vuln …` list removed** | no advisories left to ignore; any future advisory fails the build again |

`FORMS_URLFIELD_ASSUME_HTTPS` was *not* used on purpose: it is itself deprecated in 5.2.

## Compatibility checked, no code change needed

- **whitenoise 6.12** — `CompressedManifestStaticFilesStorage` works; `collectstatic`
  and the production-settings template engine smoke test pass.
- **django-q2 1.11.1** — ORM broker, `Q_CLUSTER` keys unchanged, worker/retry tests pass.
- **django-environ 0.14**, **pandas 3.1**, **Pillow 13**, **psycopg 3** — no API used by
  this project changed.
- **Deprecated/removed APIs** grep found nothing to fix: no `ugettext`, `force_text`,
  `providing_args`, `NullBooleanField`, `USE_L10N`, `index_together`, `pytz`,
  `timezone.utc`, `is_dst`, or `request.META['HTTP_*']` usage anywhere in `students/`,
  `platform_admin/` or `college_ums/`.
- **Migrations** — `makemigrations --check --dry-run`: *No changes detected*. The 5.2
  upgrade needs no schema migration.

## Verification (all run on 5.2.19)

```bash
.venv/bin/python -W error::DeprecationWarning manage.py check      # no issues, zero warnings
.venv/bin/python -W error::DeprecationWarning manage.py test       # 353 tests OK
DEBUG=False … manage.py check --deploy                             # no issues
manage.py makemigrations --check --dry-run                         # No changes detected
pip-audit -r requirements.txt                                      # No known vulnerabilities found
bandit -r … -ll -x "*/tests/*,…"                                    # 0 medium+
./scripts/ci.sh                                                    # CI mirror finished OK
scripts/rc_flows.py against Postgres + DEBUG=False                 # 112/112 checks
```

`python -W error::DeprecationWarning manage.py test` is the useful guard here: it turns
any deprecation triggered by our own code path into a failure, so the next upgrade
(6.0) starts from a clean sheet.

## Notes for the next upgrade (6.0)

- `URLField` already behaves as https (we set it explicitly); the transitional setting is
  gone in 6.0.
- `django-q2` 1.11.1 is the current line; check its 6.0 support before jumping.
- Python 3.14 is what the local venv runs; the deployment image is 3.12. Django 5.2
  supports both.
