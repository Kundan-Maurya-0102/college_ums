# Operations — background jobs & failure handling

## Background jobs (django-q2, ORM broker)

No Redis needed: the queue lives in the same database (`django_q_ormq` + `django_q_task`
tables). Suitable for 1–3 colleges per server; switch `Q_CLUSTER` to a Redis broker if you
outgrow it.

```bash
# development
.venv/bin/python manage.py qcluster

# production (docker compose)
docker compose -p <slug> -f docker-compose.prod.yml up -d worker
docker compose -p <slug> -f docker-compose.prod.yml logs -f worker
```

`docker-compose.prod.yml` runs the worker as its own service so slow outbound calls never
hold a gunicorn worker.

### What runs in the queue

| Task | Used for | Retries |
|---|---|---|
| `students.tasks.send_email_task` | notices, fee reminders | 3, backoff 1s→2s→4s on SMTP/network errors |
| `students.tasks.send_whatsapp_task` | credentials, reminders | 3, backoff on timeout/connection/429/5xx |
| `students.tasks.send_credentials_task` | WhatsApp set-password link per student | idem |

`students.tasks.notify(channel, to, subject, body)` is the single entry point:

```python
from students import tasks
status, detail = tasks.notify("whatsapp", profile.phone, body="Fee due 15 Nov")
# ("queued", "<task id>")  — worker will deliver
# ("ran",    "sent (SM...)" / "skipped (no credentials)")
# ("failed", "<reason>")   — never raises into the request
```

If the broker is unreachable (worker down, DB locked), `enqueue()` logs a warning and runs
the job **inline** so the user still gets the e-mail/WhatsApp instead of an error page.

### Retry behaviour

Retries are implemented inside the job (`students/tasks.py:with_retries`) rather than by
broker re-delivery, so timing is deterministic:

- retryable: `timeout`, `timed out`, `connection`, `temporarily`, `429`, `502`, `503`, `504`
- permanent (missing credentials, bad number, auth error): **no** retry, result recorded
- attempts: `TASK_MAX_ATTEMPTS` (default 3), backoff 1s → 2s → 4s

Verified against a real worker with an unreachable SMTP server:

```
processing ... 'students.tasks.send_email_task'
send_mail failed ([Errno 111] Connection refused); retry 1/3 in 1s
send_mail failed ([Errno 111] Connection refused); retry 2/3 in 2s
```

…after which the failure is stored in the `Failure` table and the web request was unaffected.

### Monitoring

```python
from django_q.models import Task, Failure, Success
Failure.objects.count()            # should stay at 0 in a healthy install
Task.objects.filter(started__gte=<date>)  # queue throughput
```
Django admin → *Django Q* → *Failures* lists the exception for each failed job.

## Third-party services down → app keeps working

| Dependency | Behaviour when it is down |
|---|---|
| SMTP server | job retries 3×, failure logged, user sees "queued/sent later", no 500 |
| Twilio/WhatsApp | same; credentials missing ⇒ `skipped (no credentials)` |
| Gemini (chatbot) | `students/ai_helper.py` returns the offline FAQ answer (`[Offline Mode] …`) |
| CSV parser crash | view catches it, upload marked failed, page shows *"Import fail ho gaya…"* instead of a 500 (`students/views/imports.py`) |
| Database | `/healthz/` stays DB-free so the load balancer sees liveness; errors render `500.html` without tracebacks |

Outbound calls all carry timeouts: `EMAIL_TIMEOUT` (10s), `HTTP_TIMEOUT` (Twilio/gateways,
10s), `Q_TIMEOUT` (hard kill of a task, 120s).

## Error pages

Custom `403.html`, `404.html`, `500.html` extend the branded shell, show no stack traces or
internal paths, and never echo request data. Covered by `students/tests/test_tasks.py`
(`test_error_page_hides_traceback`) and `test_ops.py`.

## Backups

See `docs/BACKUP_RESTORE.md` (encrypted dump, tested restore, 6-monthly drill).
Remember to back up **media** as well if study material/banners matter:
`tar czf media.tar.gz media/` next to the DB dump.
