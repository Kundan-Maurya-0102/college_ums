"""PWA + static-asset contract tests."""
import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from students.models import StudentProfile

STATIC = Path(settings.BASE_DIR) / "static"


class ServiceWorkerTests(TestCase):
    def test_service_worker_is_served_from_root_with_scope_header(self):
        response = self.client.get("/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response["Content-Type"])
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("const CACHE", response.content.decode())

    def test_service_worker_points_at_offline_url(self):
        body = self.client.get("/sw.js").content.decode()
        self.assertIn(reverse("offline"), body)
        self.assertNotIn("{{", body)  # template fully rendered

    def test_offline_page_renders(self):
        response = self.client.get(reverse("offline"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You are offline")


class ManifestTests(TestCase):
    def test_manifest_is_valid_json_with_required_fields(self):
        response = self.client.get(reverse("manifest"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("manifest+json", response["Content-Type"])
        data = json.loads(response.content)
        self.assertEqual(data["start_url"], "/")
        self.assertEqual(data["display"], "standalone")
        sizes = {icon["sizes"] for icon in data["icons"]}
        self.assertIn("192x192", sizes)
        self.assertIn("512x512", sizes)
        self.assertTrue(any(icon.get("purpose") == "maskable" for icon in data["icons"]))

    def test_manifest_icons_exist(self):
        data = json.loads(self.client.get(reverse("manifest")).content)
        from django.contrib.staticfiles import finders

        for icon in data["icons"]:
            found = finders.find(icon["src"].split("/static/", 1)[1])
            self.assertTrue(found, f"missing icon {icon['src']}")
            self.assertGreater(Path(found).stat().st_size, 500)


class PwaWiringTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("pwa_admin", password="TestPass!2345")

    def test_base_template_links_manifest_and_registers_worker(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_dashboard"))
        body = response.content.decode()
        self.assertIn('rel="manifest"', body)
        self.assertIn(reverse("manifest"), body)
        self.assertIn("apple-touch-icon", body)
        self.assertIn("serviceWorker", body)
        self.assertIn("/sw.js", body)

    def test_list_table_is_marked_for_client_side_tools(self):
        user = User.objects.create_user("pwa_student", password="TestPass!2345")
        StudentProfile.objects.create(user=user, name="Pwa Student", phone="9876543210",
                                      registration_number="PW001", branch="CS", semester=1)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("student_list"))
        self.assertContains(response, 'class="data-table"')
        table_js = (STATIC / "js" / "tables.js").read_text()
        self.assertIn("table.data-table", table_js)
