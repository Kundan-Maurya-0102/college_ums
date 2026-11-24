"""Password hashers tuned per deployment.

bcrypt is much cheaper than PBKDF2-SHA256 at Django's default work factor, which
matters when many users log in at the same time. Rounds are configurable so a
small VPS can trade cost for latency (`BCRYPT_ROUNDS`, default 12).
"""
from django.conf import settings
from django.contrib.auth.hashers import BCryptSHA256PasswordHasher


class TunableBCryptSHA256PasswordHasher(BCryptSHA256PasswordHasher):
    rounds = getattr(settings, "BCRYPT_ROUNDS", 12)
