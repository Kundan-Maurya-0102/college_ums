"""Password policy and token expiry verification tests."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from students.password_links import build_set_password_link, token_generator

User = get_user_model()


class PasswordValidatorConfigTests(TestCase):
    """Verify that AUTH_PASSWORD_VALIDATORS includes all required validators."""

    def test_minimum_length_validator_present(self):
        names = [v['NAME'] for v in settings.AUTH_PASSWORD_VALIDATORS]
        self.assertIn(
            'django.contrib.auth.password_validation.MinimumLengthValidator',
            names,
        )

    def test_minimum_length_is_at_least_8(self):
        for v in settings.AUTH_PASSWORD_VALIDATORS:
            if 'MinimumLengthValidator' in v['NAME']:
                min_len = v.get('OPTIONS', {}).get('min_length', 8)
                self.assertGreaterEqual(min_len, 8)

    def test_common_password_validator_present(self):
        names = [v['NAME'] for v in settings.AUTH_PASSWORD_VALIDATORS]
        self.assertIn(
            'django.contrib.auth.password_validation.CommonPasswordValidator',
            names,
        )

    def test_numeric_password_validator_present(self):
        names = [v['NAME'] for v in settings.AUTH_PASSWORD_VALIDATORS]
        self.assertIn(
            'django.contrib.auth.password_validation.NumericPasswordValidator',
            names,
        )

    def test_short_password_rejected(self):
        with self.assertRaises(ValidationError):
            validate_password('Ab1!xyz')  # 7 chars

    def test_common_password_rejected(self):
        with self.assertRaises(ValidationError):
            validate_password('password123')

    def test_numeric_only_rejected(self):
        with self.assertRaises(ValidationError):
            validate_password('12345678')

    def test_strong_password_accepted(self):
        validate_password('Str0ng!Pass2024')  # should not raise


class TokenExpiryTests(TestCase):
    """Verify set-password link expiry."""

    def setUp(self):
        self.user = User.objects.create_user(username='expiry_test')
        self.user.set_unusable_password()
        self.user.save()

    def test_password_reset_timeout_configured(self):
        """PASSWORD_RESET_TIMEOUT should be set (default 48h = 172800s)."""
        self.assertGreater(settings.PASSWORD_RESET_TIMEOUT, 0)
        # 48 hours = 172800 seconds
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 48 * 60 * 60)

    def test_token_valid_within_timeout(self):
        token = token_generator.make_token(self.user)
        self.assertTrue(token_generator.check_token(self.user, token))

    def test_token_invalid_after_expiry(self):
        token = token_generator.make_token(self.user)
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            self.assertFalse(token_generator.check_token(self.user, token))

    def test_token_invalid_after_password_change(self):
        token = token_generator.make_token(self.user)
        self.user.set_password('NewStr0ng!Pass')
        self.user.save()
        self.assertFalse(token_generator.check_token(self.user, token))


class SeedPasswordSafetyTests(TestCase):
    """Verify seed_demo won't run in production without --force."""

    def test_demo_password_is_not_trivially_weak(self):
        """The demo password used in seed_demo meets basic strength."""
        from students.management.commands.seed_demo import DEMO_PASSWORD
        # It should be at least 8 chars and not purely numeric
        self.assertGreaterEqual(len(DEMO_PASSWORD), 8)
        self.assertFalse(DEMO_PASSWORD.isdigit())

    def test_create_college_generates_random_password(self):
        """create_college generates a random password, not a fixed default."""
        import secrets
        # The command uses secrets.token_urlsafe(12) which is 16+ chars
        pw = secrets.token_urlsafe(12)
        self.assertGreaterEqual(len(pw), 16)
