from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from students.models import StudentProfile
from students.password_links import build_set_password_link, token_generator


def split_link(link):
    parts = urlparse(link).path.strip("/").split("/")
    # /set-password/<uidb64>/<token>/
    return parts[1], parts[2]


class SetPasswordTokenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cs003")
        self.user.set_unusable_password()
        self.user.save()
        self.profile = StudentProfile.objects.create(
            user=self.user,
            name="Asha",
            phone="9876543210",
            registration_number="CS003",
            is_password_changed=False,
        )

    def test_link_is_built_for_the_configured_portal(self):
        link = build_set_password_link(self.user)
        self.assertTrue(link.startswith("http"))
        self.assertIn("/set-password/", link)
        _, token = split_link(link)
        self.assertTrue(token_generator.check_token(self.user, token))

    def test_token_is_invalidated_after_password_change(self):
        link = build_set_password_link(self.user)
        _, token = split_link(link)

        self.user.set_password("Str0ngPass!2024")
        self.user.save()
        self.assertFalse(token_generator.check_token(self.user, token))

    def test_token_expires_after_configured_timeout(self):
        link = build_set_password_link(self.user)
        _, token = split_link(link)

        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            self.assertFalse(token_generator.check_token(self.user, token))


class SetPasswordViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cs004")
        self.user.set_unusable_password()
        self.user.save()
        self.profile = StudentProfile.objects.create(
            user=self.user,
            name="Ravi",
            phone="9876543210",
            registration_number="CS004",
            is_password_changed=False,
        )
        self.link = build_set_password_link(self.user)

    def test_get_with_valid_token_shows_form(self):
        response = self.client.get(self.link)
        self.assertEqual(response.status_code, 200)

    def test_post_sets_password_and_marks_profile(self):
        response = self.client.post(
            self.link,
            {"new_password1": "Str0ngPass!2024", "new_password2": "Str0ngPass!2024"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertTrue(self.user.check_password("Str0ngPass!2024"))
        self.assertTrue(self.profile.is_password_changed)

    def test_token_cannot_be_reused(self):
        data = {"new_password1": "Str0ngPass!2024", "new_password2": "Str0ngPass!2024"}
        self.client.post(self.link, data)
        second = self.client.get(self.link)
        self.assertEqual(second.status_code, 302)
        self.assertIn("/login/", second["Location"])

    def test_invalid_token_redirects_to_login(self):
        response = self.client.get("/set-password/bad-uid/bad-token/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])
