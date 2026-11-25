#!/usr/bin/env python
"""Release-candidate walkthrough: every role's main flows against a live server.

Not a unit test — it drives the real HTTP surface of a running deployment
(gunicorn + Postgres + DEBUG=False), the way a person clicking through the site
would. Each step prints PASS/FAIL; the exit code is non-zero if anything failed.

    python scripts/rc_flows.py --base-url http://127.0.0.1:8890 \
        --admin admin:RcAdmin@12345 --teacher demo_teacher1:Demo@12345 \
        --student demo_student1:Demo@12345 --parent demo_parent:Parent@12345

Credentials can also come from RC_ADMIN / RC_TEACHER / RC_STUDENT / RC_PARENT.
No third-party dependency: cookies + CSRF are handled with urllib.
"""
import argparse
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

RESULTS = []


class Session:
    """A tiny browser: cookie jar, CSRF token extraction, form posting."""

    def __init__(self, base_url):
        self.base = base_url.rstrip('/')
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            NoRedirect(),
        )

    def get(self, path, allow_redirects=False):
        return self._request('GET', path, allow_redirects=allow_redirects)

    def post(self, path, data, allow_redirects=False):
        return self._request('POST', path, data=data, allow_redirects=allow_redirects)

    def _request(self, method, path, data=None, allow_redirects=False):
        url = path if path.startswith('http') else self.base + path
        body = None
        headers = {'User-Agent': 'rc-flows/1.0'}
        if data is not None:
            body = urllib.parse.urlencode(data).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=30)
            status, location, text = response.status, response.headers.get('Location'), response.read()
        except urllib.error.HTTPError as exc:
            status, location, text = exc.code, exc.headers.get('Location'), exc.read()
        except urllib.error.URLError as exc:
            raise RuntimeError(f'{method} {url} failed: {exc}') from exc
        if allow_redirects and status in (301, 302, 303, 307, 308) and location:
            return self.get(location)
        return Response(status, location, text.decode('utf-8', 'ignore'))

    def csrf(self, path):
        body = self.get(path).body
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', body)
        return match.group(1) if match else ''

    def login(self, username, password, login_path='/login/'):
        token = self.csrf(login_path)
        response = self.post(login_path, {
            'csrfmiddlewaretoken': token, 'username': username, 'password': password,
        })
        return response


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # surface 3xx to the caller instead of following silently


class Response:
    def __init__(self, status, location, body):
        self.status, self.location, self.body = status, location, body

    @property
    def is_html(self):
        return '<html' in self.body[:400].lower()


def check(name, condition, detail=''):
    ok = bool(condition)
    RESULTS.append((ok, name, detail))
    print(('  PASS  ' if ok else '  FAIL  ') + name + (f'  [{detail}]' if detail and not ok else ''))
    return ok


def expect_status(name, response, allowed, detail=''):
    return check(name, response.status in allowed,
                 detail or f'status={response.status} location={response.location}')


def role_admin(base, creds):
    print('\n== admin ==')
    session = Session(base)
    response = session.login(*creds)
    expect_status('admin login redirects', response, (302,), f'{response.status} {response.location}')
    check('admin lands on /admin-panel/', response.location == '/admin-panel/', str(response.location))

    # marker = a phrase the real page shows (lowercase, matched case-insensitively)
    pages = {
        '/admin-panel/': 'dashboard',
        '/admin-panel/students/': 'all students',
        '/admin-panel/teachers/': 'teacher',
        '/admin-panel/subjects/': 'subject',
        '/admin-panel/notices/': 'notice',
        '/admin-panel/fee-payments/': 'fee payment',
        '/admin-panel/fees/': 'fee',
        '/admin-panel/attendance/': 'attendance',
        '/admin-panel/take-attendance/': 'attendance',
        '/admin-panel/marks/': 'marks',
        '/admin-panel/reports/': 'report',
        '/admin-panel/admins/': 'admin',
        '/admin-panel/upload/': 'csv',
        '/admin-panel/upload-history/': 'upload history',
        '/admin-panel/bug-reports/': 'report',
        '/banners/': 'banner',
        '/admin/': None,
    }
    for path, marker in pages.items():
        response = session.get(path)
        if response.status in (301, 302) and path in ('/admin/',):
            check(f'admin GET {path}', True, 'redirect (fine)')
            continue
        ok = expect_status(f'admin GET {path}', response, (200,))
        if ok and marker:
            check(f'  {path} renders "{marker}"', marker in response.body.lower())

    csv_response = session.get('/admin-panel/students/export/')
    check('students CSV export downloads', csv_response.status == 200
          and 'DEMO0001' in csv_response.body, str(csv_response.status))

    # create a notice (real form POST with CSRF)
    token = session.csrf('/admin-panel/notices/create/')
    response = session.post('/admin-panel/notices/create/', {
        'csrfmiddlewaretoken': token, 'title': 'RC release notice',
        'content': 'Release candidate walkthrough notice.', 'target_branches': '',
        'target_semesters': '', 'is_active': 'on',
    })
    check('admin creates a notice', response.status in (200, 302, 303),
          f'{response.status} {response.body[:200]}')

    response = session.get('/admin-panel/notices/')
    check('notice appears in the list', 'RC release notice' in response.body)

    # add a single student (flat form)
    student_form = session.get('/admin-panel/students/add/')
    check('add-student form loads', student_form.status == 200)
    token = session.csrf('/admin-panel/students/add/')
    response = session.post('/admin-panel/students/add/', {
        'csrfmiddlewaretoken': token, 'name': 'RC Walkthrough Student',
        'registration_number': 'RCW0001', 'branch': 'CS', 'semester': '3',
        'year_of_admission': '2024', 'phone': '9000000001',
        'father_name': '', 'mother_name': '', 'email': '', 'address': '',
    })
    check('admin adds a student', response.status in (200, 302, 303),
          f'{response.status} {response.body[:300]}')
    check('new student is searchable',
          'RC Walkthrough Student' in session.get('/admin-panel/students/?q=RCW0001').body)

    # bug-report triage page reachable, and the platform overview
    check('platform overview reachable', session.get('/platform/').status == 200)
    check('system status page reachable', session.get('/admin-panel/system-status/').status == 200)


def role_teacher(base, creds):
    print('\n== teacher ==')
    session = Session(base)
    response = session.login(*creds)
    expect_status('teacher login redirects', response, (302,))
    check('teacher lands on /teacher/', response.location == '/teacher/', str(response.location))

    for path, marker in {
        '/teacher/': 'Dashboard',
        '/teacher/students/': None,
        '/teacher/attendance/': None,
        '/teacher/marks/': None,
        '/teacher/materials/': None,
        '/teacher/assignments/': None,
        '/teacher/notices/': None,
        '/teacher/schedule/': None,
    }.items():
        response = session.get(path)
        expect_status(f'teacher GET {path}', response, (200,))
        if marker:
            check(f'  {path} renders "{marker}"', marker in response.body)

    token = session.csrf('/teacher/materials/')
    response = session.post('/teacher/materials/', {
        'csrfmiddlewaretoken': token, 'title': 'RC material',
        'description': 'Release candidate note', 'subject': '',
        'material_type': 'NOTE', 'link': '',
    })
    check('teacher material form responds', response.status in (200, 302, 403),
          f'{response.status}')

    # attendance marking page must list the teacher's own class
    attendance = session.get('/teacher/attendance/')
    check('teacher attendance page has students or a selector',
          attendance.status == 200 and
          ('student' in attendance.body.lower() or 'select' in attendance.body.lower()))


def role_student(base, creds):
    print('\n== student ==')
    session = Session(base)
    response = session.login(*creds)
    expect_status('student login redirects', response, (302,))
    landing = response.location
    check('student lands on dashboard or password change',
          landing in ('/dashboard/', '/change-password/'), str(landing))

    for path, marker in {
        '/dashboard/': 'Dashboard',
        '/my-fees/': 'Fee',
        '/exam-schedule/': 'Exam',
        '/certificates/': 'Certificate',
        '/events/': 'Event',
        '/leave-apply/': 'Leave',
        '/feedback/': 'Feedback',
        '/forum/': 'Doubt',
        '/profile/edit/': None,
        '/change-password/': None,
    }.items():
        response = session.get(path)
        if response.status == 302 and path == '/dashboard/':
            check(f'student GET {path}', True, 'redirect (password change pending)')
            continue
        expect_status(f'student GET {path}', response, (200,))
        if marker and response.status == 200:
            check(f'  {path} renders "{marker}"', marker in response.body)

    token = session.csrf('/leave-apply/')
    response = session.post('/leave-apply/', {
        'csrfmiddlewaretoken': token, 'from_date': '2026-01-05', 'to_date': '2026-01-06',
        'reason': 'RC walkthrough leave request',
    })
    check('student applies for leave', response.status in (200, 302, 303), f'{response.status}')

    certificate = session.get('/certificates/?type=bonafide')
    check('student prints a bonafide certificate',
          certificate.status == 200 and 'BONAFIDE' in certificate.body.upper())

    check('student cannot open the admin panel',
          session.get('/admin-panel/').status in (302, 403))
    check('student cannot open the teacher panel',
          session.get('/teacher/').status in (302, 403))
    check('student cannot download the CSV inbox',
          session.get('/media/csv_uploads/anything.csv').status in (302, 404))


def role_parent(base, creds):
    print('\n== parent ==')
    session = Session(base)
    response = session.login(*creds)
    expect_status('parent login redirects', response, (302,))
    check('parent lands on /parent/', response.location == '/parent/', str(response.location))

    dashboard = session.get('/parent/')
    expect_status('parent dashboard', dashboard, (200,))
    check('parent dashboard lists a child', 'DEMO0001' in dashboard.body or 'Child' in dashboard.body)
    post_targets = re.findall(r'<form[^>]+action="([^"]*)"[^>]*method="post"', dashboard.body.lower())
    check('parent portal has no write actions',
          not any(t for t in post_targets if t and 'i18n' not in t),
          f'forms posting to {post_targets}')

    match = re.search(r'/parent/child/(\d+)/', dashboard.body)
    check('parent dashboard links to a child', bool(match))
    if match:
        child = session.get(f'/parent/child/{match.group(1)}/')
        expect_status('parent child page', child, (200,))
        check('child page shows marks or an empty state',
              'Marks' in child.body or 'NO MARKS' in child.body.upper())

    check('parent cannot open the admin panel',
          session.get('/admin-panel/').status in (302, 403))
    check('parent cannot open the student dashboard',
          session.get('/dashboard/').status in (302, 403))


def role_super_admin(base, creds):
    print('\n== super admin (platform) ==')
    session = Session(base)
    session.login(*creds)
    for path, marker in {
        '/platform/': 'College',
        '/platform/colleges/': 'College',
        '/platform/plans/': 'Plan',
        '/platform/usage/': 'Usage',
        '/platform/tickets/': 'Ticket',
    }.items():
        response = session.get(path)
        expect_status(f'super admin GET {path}', response, (200,))
        if response.status == 200 and marker:
            check(f'  {path} mentions "{marker}"', marker.lower() in response.body.lower())

    # metrics API: this deployment's own token
    token = os.environ.get('RC_METRICS_TOKEN') or os.environ.get('PLATFORM_METRICS_TOKEN', '')
    if token:
        data = json.dumps({'student_count': 51}).encode()
        request = urllib.request.Request(
            base + '/platform/metrics/rc-test/', data=data, method='POST',
            headers={'Content-Type': 'application/json', 'X-Platform-Token': token})
        try:
            status = urllib.request.urlopen(request, timeout=15).status
        except urllib.error.HTTPError as exc:
            status = exc.code
        check('metrics endpoint accepts the college token', status == 200, f'status={status}')
    else:
        print('  SKIP  metrics endpoint (set RC_METRICS_TOKEN)')


def anonymous(base):
    print('\n== anonymous ==')
    session = Session(base)
    for path, allowed in {
        '/login/': (200,), '/privacy/': (200,), '/terms/': (200,),
        '/healthz/': (200,), '/readyz/': (200,),
        '/': (200, 301, 302),
        '/admin-panel/': (301, 302), '/dashboard/': (301, 302),
        '/parent/': (301, 302), '/platform/': (301, 302),
    }.items():
        expect_status(f'anon GET {path}', session.get(path), allowed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default=os.environ.get('RC_BASE_URL', 'http://127.0.0.1:8000'))
    parser.add_argument('--admin', default=os.environ.get('RC_ADMIN', 'admin:RcAdmin@12345'))
    parser.add_argument('--teacher', default=os.environ.get('RC_TEACHER', 'demo_teacher1:Demo@12345'))
    parser.add_argument('--student', default=os.environ.get('RC_STUDENT', 'demo_student1:Demo@12345'))
    parser.add_argument('--parent', default=os.environ.get('RC_PARENT', 'demo_parent:Parent@12345'))
    parser.add_argument('--skip', default='', help='comma list: admin,teacher,student,parent,super,anonymous')
    args = parser.parse_args()

    def creds(value):
        username, _, password = value.partition(':')
        return username, password

    started = time.time()
    skip = {s.strip() for s in args.skip.split(',') if s.strip()}
    runners = {
        'anonymous': lambda: anonymous(args.base_url),
        'admin': lambda: role_admin(args.base_url, creds(args.admin)),
        'teacher': lambda: role_teacher(args.base_url, creds(args.teacher)),
        'student': lambda: role_student(args.base_url, creds(args.student)),
        'parent': lambda: role_parent(args.base_url, creds(args.parent)),
        'super': lambda: role_super_admin(args.base_url, creds(args.admin)),
    }
    print(f'RC walkthrough against {args.base_url}')
    for name in ('anonymous', 'admin', 'teacher', 'student', 'parent', 'super'):
        if name in skip:
            print(f'\n== {name} == skipped')
            continue
        try:
            runners[name]()
        except Exception as exc:  # a role crashing is a finding, not a stack trace dump
            check(f'{name} role completed', False, f'crash: {exc}')

    passed = sum(1 for ok, _, _ in RESULTS if ok)
    failed = [(n, d) for ok, n, d in RESULTS if not ok]
    print(f'\n{passed}/{len(RESULTS)} checks passed in {time.time() - started:.1f}s')
    if failed:
        print('\nFAILURES:')
        for name, detail in failed:
            print(f'  - {name}' + (f'  [{detail}]' if detail else ''))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
