"""Concurrency / load test for College UMS (no external dependencies).

Each virtual user logs in, then loops through the hot pages (dashboard, students,
attendance, fees, notices) and reports latency percentiles.

    # start the server first, e.g. gunicorn with 4 workers:
    #   .venv/bin/gunicorn college_ums.wsgi:application --bind 127.0.0.1:8899 --workers 4
    .venv/bin/python scripts/load_test.py --url http://127.0.0.1:8899 --users 100 --iterations 10

    # login-only smoke:
    .venv/bin/python scripts/load_test.py --url ... --users 100 --iterations 1

Output: requests/s, p50/p95/p99 latency, status code counts, slowest page.
Exit code 1 if any request errors.
"""
import argparse
import http.cookiejar
import re
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

PAGES = [
    ("/admin-panel/", "dashboard"),
    ("/admin-panel/students/", "students"),
    ("/admin-panel/take-attendance/", "attendance"),
    ("/admin-panel/fee-payments/", "fees"),
    ("/admin-panel/notices/", "notices"),
]

TOKEN_RE = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')


class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.latencies = defaultdict(list)
        self.statuses = Counter()
        self.errors = []

    def add(self, label, elapsed_ms, status, error=None):
        with self.lock:
            self.latencies[label].append(elapsed_ms)
            self.statuses[status] += 1
            if error:
                self.errors.append(error)


def percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return ordered[index]


def make_opener(host):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", "ums-loadtest/1.0"), ("Host", host)]
    return opener


def fetch(opener, url, timeout=30):
    started = time.perf_counter()
    try:
        with opener.open(url, timeout=timeout) as response:
            body = response.read()
            return response.status, body, (time.perf_counter() - started) * 1000
    except urllib.error.HTTPError as exc:
        return exc.code, b"", (time.perf_counter() - started) * 1000
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        return 0, b"", (time.perf_counter() - started) * 1000, str(exc)


def login(opener, base, username, password):
    status, body, ms = fetch(opener, f"{base}/login/")
    if status != 200:
        return status, ms, f"login page returned {status}"
    match = TOKEN_RE.search(body.decode("utf-8", "ignore"))
    if not match:
        return status, ms, "csrf token not found on login page"
    data = urllib.parse.urlencode({
        "csrfmiddlewaretoken": match.group(1),
        "username": username,
        "password": password,
    }).encode()
    request = urllib.request.Request(f"{base}/login/", data=data)
    request.add_header("Referer", f"{base}/login/")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    started = time.perf_counter()
    try:
        with opener.open(request, timeout=30) as response:
            elapsed = (time.perf_counter() - started) * 1000
            return response.status, elapsed, None
    except urllib.error.HTTPError as exc:
        return exc.code, (time.perf_counter() - started) * 1000, None
    except Exception as exc:  # noqa: BLE001
        return 0, (time.perf_counter() - started) * 1000, str(exc)


def virtual_user(idx, base, host, username, password, iterations, stats, stop_at):
    opener = make_opener(host)
    status, ms, error = login(opener, base, username, password)
    stats.add("login", ms, status, f"user {idx}: {error}" if error else None)
    if status not in (200, 302):
        return
    for _ in range(iterations):
        if stop_at and time.time() > stop_at:
            return
        for path, label in PAGES:
            status, _body, ms, *rest = fetch(opener, f"{base}{path}")
            stats.add(label, ms, status, rest[0] if rest else None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="Admin@12345")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    base = args.url.rstrip("/")
    host = urllib.parse.urlparse(base).netloc
    stats = Stats()
    stop_at = time.time() + args.timeout

    print(f"load: {args.users} virtual users x {args.iterations} rounds against {base}")
    threads = [
        threading.Thread(target=virtual_user,
                         args=(i, base, host, args.username, args.password,
                               args.iterations, stats, stop_at),
                         daemon=True)
        for i in range(args.users)
    ]

    started = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    wall = time.perf_counter() - started

    all_latencies = [value for values in stats.latencies.values() for value in values]
    total = sum(stats.statuses.values())
    errors = {code: count for code, count in stats.statuses.items() if code >= 400 or code == 0}

    print(f"\nfinished in {wall:.2f}s — {total} requests, {total / wall:.1f} req/s")
    print(f"status codes: {dict(sorted(stats.statuses.items()))}")
    if errors:
        print(f"ERRORS: {errors}")
        for message in stats.errors[:10]:
            print(f"  - {message}")

    print(f"\n{'page':<14} {'count':>6} {'p50':>8} {'p95':>8} {'p99':>8} {'max':>8}")
    print("-" * 56)
    for label, values in sorted(stats.latencies.items()):
        print(f"{label:<14} {len(values):>6} {percentile(values, 50):>7.1f}ms "
              f"{percentile(values, 95):>7.1f}ms {percentile(values, 99):>7.1f}ms "
              f"{max(values):>7.1f}ms")

    print(f"\noverall      {len(all_latencies):>6} {percentile(all_latencies, 50):>7.1f}ms "
          f"{percentile(all_latencies, 95):>7.1f}ms {percentile(all_latencies, 99):>7.1f}ms "
          f"{max(all_latencies):>7.1f}ms")
    if len(all_latencies) > 1:
        print(f"mean {statistics.mean(all_latencies):.1f}ms, "
              f"stdev {statistics.pstdev(all_latencies):.1f}ms")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
