from django.contrib.auth.models import User
from django.test import TestCase

from students.models import Notice


class PaginationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="office_admin", password="TestPass!2345", is_staff=True
        )
        self.client.force_login(self.admin)
        for i in range(30):
            Notice.objects.create(title=f"Notice {i:02d}", content="body", is_active=True)

    def test_first_page_shows_page_size(self):
        response = self.client.get("/admin-panel/notices/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["notices"]), 25)
        self.assertEqual(response.context["notices"].paginator.count, 30)

    def test_second_page_shows_rest(self):
        response = self.client.get("/admin-panel/notices/?page=2")
        self.assertEqual(len(response.context["notices"]), 5)

    def test_invalid_page_falls_back_to_first(self):
        response = self.client.get("/admin-panel/notices/?page=abc")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["notices"].number, 1)

    def test_out_of_range_page_falls_back_to_last(self):
        response = self.client.get("/admin-panel/notices/?page=999")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["notices"].number, 2)

    def test_filter_is_kept_in_pagination_links(self):
        response = self.client.get("/admin-panel/leave-applications/?status=PENDING")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("status=PENDING", html)


class ErrorPageTests(TestCase):
    def test_unknown_url_uses_custom_404(self):
        response = self.client.get("/definitely-not-a-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)
