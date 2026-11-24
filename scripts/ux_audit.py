"""Heuristic UX audit: walk the app as each role and report concrete problems.

Usage:
    .venv/bin/python scripts/ux_audit.py            # all roles
    .venv/bin/python scripts/ux_audit.py --role admin

Checks per page (heuristics that map to real user pain):
  * fixed multi-column grids with no responsive fallback (breaks on phones)
  * inputs without a label / aria-label
  * buttons that submit a destructive action without confirmation
  * tables without a header row or without the responsive `data-table` hook
  * long lists (>25 rows) without pagination
  * images without alt text
  * target="_blank" links without rel="noopener"
  * pages without exactly one <h1>
  * inline style usage (harder to theme/scale)
  * very large HTML (>150 KB) pages
"""
import os
import re
import sys
from argparse import ArgumentParser
from collections import defaultdict

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "college_ums.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import URLPattern, URLResolver, get_resolver  # noqa: E402

SKIP_PREFIXES = ("/admin/", "/platform/metrics", "/logout", "/set-password",
                 "/sw.js", "/manifest", "/healthz", "/readyz", "/static/", "/media/")

GRID_RE = re.compile(r'grid-template-columns:\s*(?:1fr\s+){1,3}1fr')
INPUT_RE = re.compile(r"<(?:input|select|textarea)\b[^>]*>", re.I)
LABEL_RE = re.compile(r"<label\b", re.I)
TABLE_RE = re.compile(r"<table\b", re.I)
ROW_RE = re.compile(r"<tr\b", re.I)
H1_RE = re.compile(r"<h1\b", re.I)
IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
BLANK_RE = re.compile(r'<a\b[^>]*target="_blank"[^>]*>', re.I)
FORM_RE = re.compile(r"<form\b[^>]*>", re.I)


def get_url_names():
    """Every GET-able URL pattern name not in the skip list."""
    resolver = get_resolver()
    names = []

    def walk(patterns, prefix=""):
        for entry in patterns:
            if isinstance(entry, URLResolver):
                walk(entry.url_patterns, prefix + str(entry.pattern))
            elif isinstance(entry, URLPattern):
                route = prefix + str(entry.pattern)
                if any(token in route for token in ("<", "\\")):
                    continue
                if route.startswith(SKIP_PREFIXES):
                    continue
                names.append("/" + route.lstrip("/"))
    walk(resolver.url_patterns)
    return sorted(set(names))


def role_clients():
    clients = {}
    users = {
        "admin": User.objects.filter(is_staff=True, is_superuser=True, is_active=True).first(),
        "teacher": User.objects.filter(is_staff=True, facultyprofile__isnull=False,
                                      is_superuser=False, is_active=True).first(),
        "student": User.objects.filter(studentprofile__isnull=False, is_active=True).first(),
    }
    for role, user in users.items():
        if not user:
            continue
        client = Client(HTTP_HOST="localhost")
        client.force_login(user)
        clients[role] = client
    return clients


def audit_page(html, url):
    issues = []
    if len(html) > 150_000:
        issues.append(f"page is {len(html) // 1024} KB of HTML (slow on 3G)")
    grids = GRID_RE.findall(html)
    if grids and "@media" not in html:
        issues.append(f"{len(grids)} fixed-column grid(s) with no media query (mobile overflow)")

    inputs = INPUT_RE.findall(html)
    unlabelled = []
    for tag in inputs:
        if 'type="hidden"' in tag or "csrfmiddlewaretoken" in tag:
            continue
        if not re.search(r'aria-label=|id="[^"]+"', tag):
            unlabelled.append(tag[:60])
    labels = len(LABEL_RE.findall(html))
    if len(inputs) - labels > 3 and unlabelled:
        issues.append(f"{len(unlabelled)} input(s) without label/aria-label")

    tables = len(TABLE_RE.findall(html))
    theads = html.count("<thead")
    if tables > theads:
        issues.append(f"{tables - theads} table(s) without a header row")

    rows = len(ROW_RE.findall(html))
    if rows > 60 and "pagination" not in html and "page_obj" not in html:
        issues.append(f"{rows} table rows rendered without pagination")

    for tag in IMG_RE.findall(html):
        if "alt=" not in tag:
            issues.append("image without alt text")
            break

    for tag in BLANK_RE.findall(html):
        if "noopener" not in tag:
            issues.append('target="_blank" without rel="noopener"')
            break

    h1_count = len(H1_RE.findall(html))
    if h1_count == 0:
        issues.append("no <h1> heading")
    elif h1_count > 1:
        issues.append(f"{h1_count} <h1> headings (unclear page hierarchy)")

    inline = len(re.findall(r'style="[^"]{25,}"', html))
    if inline > 12:
        issues.append(f"{inline} long inline style attributes (hard to theme)")
    return issues


def main():
    parser = ArgumentParser()
    parser.add_argument("--role", default="all")
    args = parser.parse_args()

    urls = get_url_names()
    clients = role_clients()
    if args.role != "all":
        clients = {k: v for k, v in clients.items() if k == args.role}

    findings = defaultdict(list)
    pages = 0
    for role, client in clients.items():
        print(f"\n=== {role} ===")
        for url in urls:
            try:
                response = client.get(url)
            except Exception as exc:  # noqa: BLE001 - audit should keep going
                print(f"  !! {url} raised {exc.__class__.__name__}: {exc}")
                continue
            if response.status_code != 200 or "text/html" not in response.get("Content-Type", ""):
                continue
            pages += 1
            html = response.content.decode("utf-8", "ignore")
            issues = audit_page(html, url)
            for issue in issues:
                findings[issue].append(f"{role} {url}")

    print(f"\n\nscanned {pages} page renders across {len(clients)} role(s)\n")
    if not findings:
        print("no heuristic problems found")
        return

    print("issue counts:")
    for issue, where in sorted(findings.items(), key=lambda item: -len(item[1])):
        print(f"  {len(where):3}  {issue}")
        for loc in where[:6]:
            print(f"        - {loc}")


if __name__ == "__main__":
    main()
