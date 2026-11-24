"""UX regression guards: hierarchy, responsive layout, feedback, empty states.

These don't try to be pixel tests — they lock in the rules we fixed during the
Phase UX pass so they don't silently come back.
"""
import pathlib
import re

from django.contrib.auth.models import User
from django.test import Client, TestCase

TEMPLATES_DIR = pathlib.Path(__file__).resolve().parents[2] / "templates"
STATIC_CSS = pathlib.Path(__file__).resolve().parents[2] / "static" / "css" / "theme.css"


class HeadingHierarchyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("ux_admin", password="TestPass!2345", is_staff=True)

    def test_every_app_template_has_one_h1(self):
        offenders = []
        for path in sorted(TEMPLATES_DIR.rglob("*.html")):
            if path.name in ("base.html", "public_page.html", "offline.html"):
                continue
            if "partials" in path.parts:
                continue
            src = path.read_text()
            if "{% extends" not in src:
                continue
            count = len(re.findall(r"<h1\b", src))
            if count != 1:
                offenders.append(f"{path.name}: {count}")
        self.assertEqual(offenders, [], f"templates without exactly one <h1>: {offenders}")

    def test_rendered_pages_have_one_h1(self):
        client = Client(HTTP_HOST="localhost")
        client.force_login(self.admin)
        for url in ("/admin-panel/", "/admin-panel/students/", "/admin-panel/fees/",
                    "/admin-panel/reports/"):
            with self.subTest(url=url):
                html = client.get(url).content.decode()
                self.assertEqual(len(re.findall(r"<h1\b", html)), 1, url)


class ResponsiveLayoutTests(TestCase):
    def test_no_hardcoded_inline_multi_column_grids(self):
        """`style="grid-template-columns: 1fr 1fr"` overflows on phones."""
        pattern = re.compile(r'grid-template-columns:\s*(?:1fr\s+){1,3}1fr')
        offenders = []
        for path in TEMPLATES_DIR.rglob("*.html"):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if pattern.search(line) and "style=" in line:
                    offenders.append(f"{path.name}:{number}")
        self.assertEqual(offenders, [], f"inline fixed grids found: {offenders}")

    def test_grid_helpers_collapse_on_small_screens(self):
        css = STATIC_CSS.read_text()
        self.assertIn(".grid-2", css)
        self.assertIn(".grid-split", css)
        self.assertRegex(css, r"@media \(max-width: 900px\)\s*\{\s*\.grid-2")
        self.assertRegex(css, r"@media \(max-width: 1024px\)\s*\{\s*\.grid-split")

    def test_tables_have_mobile_card_labels(self):
        css = STATIC_CSS.read_text()
        self.assertIn("data-label", css)
        self.assertIn("max-width: 640px", css)

    def test_viewport_meta_present(self):
        html = self.client.get("/privacy/", HTTP_HOST="localhost").content.decode()
        self.assertIn('name="viewport"', html)


class FeedbackTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("ux_admin2", password="TestPass!2345", is_staff=True)

    def test_invalid_form_shows_errors_inline(self):
        client = Client(HTTP_HOST="localhost")
        client.force_login(self.admin)
        response = client.post("/admin-panel/notices/create/", {"title": ""})
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('id="form-errors"', body)
        self.assertIn("This field is required.", body)
        self.assertIn('href="#id_title"', body)

    def test_every_form_template_shows_validation_errors(self):
        missing = []
        for path in sorted(TEMPLATES_DIR.rglob("*.html")):
            src = path.read_text()
            if "{% csrf_token %}" not in src:
                continue
            if ("form_errors.html" not in src and "form_fields.html" not in src
                    and "errorlist" not in src):
                # partials that are not standalone forms (csrf belongs to the caller)
                if path.name in {"language_switch.html"}:
                    continue
                missing.append(path.name)
        self.assertEqual(missing, [], f"forms without error feedback: {missing}")

    def test_destructive_actions_ask_for_confirmation(self):
        css_js = (STATIC_CSS.parent.parent / "js" / "ui.js").read_text()
        self.assertIn("data-confirm", css_js)
        banners = (TEMPLATES_DIR / "admin_dashboard" / "banner_upload.html").read_text()
        self.assertIn("confirm(", banners)

    def test_submit_buttons_get_a_loading_state(self):
        ui_js = (STATIC_CSS.parent.parent / "js" / "ui.js").read_text()
        self.assertIn("is-loading", ui_js)
        css = STATIC_CSS.read_text()
        self.assertIn(".btn.is-loading", css)

    def test_toasts_are_announced_to_screen_readers(self):
        html = self.client.get("/login/", HTTP_HOST="localhost").content.decode() \
            if False else (TEMPLATES_DIR / "base.html").read_text()
        self.assertIn('role="status"', html)
        self.assertIn('aria-live="polite"', html)


class EmptyStateTests(TestCase):
    """List pages must explain what to do when there are no rows."""

    LIST_TEMPLATES = [
        "admin_dashboard/notices.html",
        "admin_dashboard/events.html",
        "admin_dashboard/fee_payments.html",
        "admin_dashboard/subjects.html",
        "admin_dashboard/students_list.html",
        "admin_dashboard/reports.html",
        "forum/doubt_list.html",
    ]

    def test_list_templates_have_empty_states(self):
        for name in self.LIST_TEMPLATES:
            with self.subTest(template=name):
                src = (TEMPLATES_DIR / name).read_text()
                self.assertTrue(
                    "empty-state" in src or "{% empty %}" in src,
                    f"{name} has no empty state")


class ExternalLinkTests(TestCase):
    def test_blank_targets_are_noopener(self):
        offenders = []
        for path in TEMPLATES_DIR.rglob("*.html"):
            html = path.read_text()
            for match in re.finditer(r'<a\b[^>]*target="_blank"[^>]*>', html):
                if "noopener" not in match.group(0):
                    offenders.append(path.name)
                    break
        self.assertEqual(offenders, [], f'target="_blank" without noopener: {offenders}')
