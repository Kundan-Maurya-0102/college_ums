from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


token_generator = PasswordResetTokenGenerator()


def build_set_password_link(user) -> str:
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = token_generator.make_token(user)
    portal_url = getattr(settings, "PORTAL_URL", "http://127.0.0.1:8000").rstrip("/")
    return f"{portal_url}/set-password/{uidb64}/{token}/"

