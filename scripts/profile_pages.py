"""Query-count profiler: how many SQL queries does each key page run?

    .venv/bin/python scripts/profile_pages.py
    .venv/bin/python scripts/profile_pages.py /admin-panel/students/ /dashboard/

Runs against the development database (read-only) with DEBUG=False so the query
counter is not polluted by debug output. Prints query counts and the slowest
queries (per-query time measured by the database wrapper).
"""
import os
import sys
import time
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "college_ums.settings")
django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.db import connection, reset_queries  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

DEFAULT_PAGES = [
    ("/admin-panel/", "admin dashboard"),
    ("/admin-panel/students/", "student list (paginated)"),
    ("/admin-panel/students/?q=Ram&branch=CS", "student list filtered"),
    ("/admin-panel/marks/", "marks entry"),
    ("/admin-panel/results/", "results view"),
    ("/admin-panel/attendance/", "manual attendance"),
    ("/admin-panel/take-attendance/", "bulk attendance"),
    ("/admin-panel/fee-payments/", "fee payments"),
    ("/admin-panel/fees/", "fee structure"),
    ("/admin-panel/notices/", "notices"),
    ("/admin-panel/teachers/", "teachers"),
    ("/admin-panel/reports/", "reports"),
    ("/admin-panel/leave-applications/", "leave requests"),
    ("/admin-panel/upload-history/", "upload history"),
]


def find_user(username="admin"):
    user = User.objects.filter(username=username).first()
    if user:
        return user
    return User.objects.filter(is_staff=True).order_by("pk").first()


def measure(client, path):
    reset_queries()
    started = time.perf_counter()
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(path)
    elapsed = (time.perf_counter() - started) * 1000
    return response.status_code, len(ctx), elapsed, ctx.captured_queries


def main(pages):
    user = find_user()
    if user is None:
        print("No staff user found — cannot profile admin pages.")
        return 1

    client = Client(HTTP_HOST="localhost")
    client.force_login(user)

    print(f"profiling as user={user.username!r} (is_staff={user.is_staff})")
    print(f"{'status':>6} {'queries':>8} {'ms':>8}  page")
    print("-" * 78)

    results = []
    for path, label in pages:
        status, count, elapsed, queries = measure(client, path)
        results.append((count, elapsed, path, label, queries))
        print(f"{status:>6} {count:>8} {elapsed:>8.1f}  {label:<28} {path}")

    print()
    print("slowest individual queries:")
    all_queries = [(q["time"], q["sql"]) for _, _, _, _, qs in results for q in qs]
    for time_s, sql in sorted(all_queries, key=lambda q: float(q[0]), reverse=True)[:8]:
        one_line = " ".join(sql.split())
        print(f"  {float(time_s) * 1000:7.1f} ms  {one_line[:120]}")

    worst = max(results, key=lambda r: r[0])
    print()
    print(f"highest query count: {worst[0]} queries on {worst[2]} ({worst[3]})")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args:
        pages = [(arg, arg) for arg in args]
    else:
        pages = DEFAULT_PAGES
    raise SystemExit(main(pages))
