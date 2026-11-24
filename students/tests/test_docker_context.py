"""Guards for the Docker build context (the path a new deploy actually takes).

`docker build` only sees files that survive `.dockerignore`. A pattern that is a
little too broad silently removes runtime assets, and the failure only appears
inside the container — never in `runserver`. These tests compare what the code
needs with what the ignore file keeps.
"""
import fnmatch
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

BASE = Path(settings.BASE_DIR)


def dockerignore_patterns():
    path = BASE / '.dockerignore'
    return [line.strip() for line in path.read_text().splitlines()
            if line.strip() and not line.strip().startswith('#')]


def ignored(rel_path):
    """True when Docker would drop this repository-relative path."""
    for pattern in dockerignore_patterns():
        clean = pattern.rstrip('/')
        candidate = clean.lstrip('/')
        if pattern.startswith('/'):          # anchored at the context root
            if '/' not in rel_path and fnmatch.fnmatch(rel_path, candidate):
                return True
        elif '/' in candidate:               # path pattern
            if fnmatch.fnmatch(rel_path, candidate) or rel_path.startswith(candidate + '/'):
                return True
        else:                                # bare name pattern: any depth
            if fnmatch.fnmatch(Path(rel_path).name, candidate):
                return True
            if fnmatch.fnmatch(rel_path, candidate) or rel_path.startswith(candidate + '/'):
                return True
    return False


class DockerContextTests(SimpleTestCase):
    def test_dockerignore_exists(self):
        self.assertTrue((BASE / '.dockerignore').exists())

    def test_runtime_static_assets_survive_the_ignore_file(self):
        """Every asset referenced by {% static %} must reach the image."""
        referenced = set()
        # {% static 'x' %} in templates and static('x') / icon('x') in python
        pattern = re.compile(r"""(?:static|icon)\(?\s*['"]([^'"]+)['"]""")
        for folder in ('templates', 'students', 'platform_admin', 'college_ums'):
            for path in (BASE / folder).rglob('*'):
                if path.suffix not in {'.html', '.py'} or not path.is_file():
                    continue
                for match in pattern.finditer(path.read_text(errors='ignore')):
                    referenced.add(match.group(1))
        self.assertTrue(referenced, 'no static references found — regex broke')

        missing_in_repo, dropped = [], []
        for ref in sorted(referenced):
            if not ref.startswith(('images/', 'css/', 'js/', 'vendor/', 'fonts/')):
                continue
            repo_path = BASE / 'static' / ref
            if not repo_path.exists():
                missing_in_repo.append(ref)       # template bug, not docker's
                continue
            if ignored(f'static/{ref}'):
                dropped.append(ref)

        self.assertEqual(dropped, [],
                         f"these referenced assets are excluded by .dockerignore: {dropped}")
        self.assertEqual(missing_in_repo, [],
                         f"templates reference files that do not exist: {missing_in_repo}")

    def test_app_code_and_templates_are_in_the_context(self):
        for rel in ('manage.py', 'entrypoint.sh', 'requirements.txt',
                    'college_ums/settings.py', 'students/models.py',
                    'templates/base.html', 'locale/hi/LC_MESSAGES/django.po',
                    'platform_admin/models.py'):
            self.assertTrue((BASE / rel).exists(), rel)
            self.assertFalse(ignored(rel), f"{rel} is excluded from the docker build")

    def test_secrets_are_not_baked_into_the_image(self):
        for rel in ('.env', 'db.sqlite3'):
            if (BASE / rel).exists():
                self.assertTrue(ignored(rel), f"{rel} must not enter the image")

    def test_entrypoint_runs_the_full_pipeline(self):
        text = (BASE / 'entrypoint.sh').read_text()
        order = ['manage.py compile_translations', 'manage.py migrate',
                 'manage.py collectstatic', 'gunicorn college_ums']
        positions = [text.index(step) for step in order]
        self.assertEqual(positions, sorted(positions), 'entrypoint steps out of order')
