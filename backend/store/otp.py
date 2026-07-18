import hashlib
import hmac
import random
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone


def generate_otp(length: int = 6) -> str:
    # Ensure leading zeros are preserved.
    return ''.join(str(random.randint(0, 9)) for _ in range(length))


def otp_hash(otp: str) -> str:
    # Hash for storage/compare.
    # Use a secret salt so plain OTP cannot be reversed.
    secret = getattr(settings, 'OTP_HASH_SECRET', None) or 'dev-otp-secret-change-me'
    digest = hmac.new(secret.encode('utf-8'), otp.encode('utf-8'), hashlib.sha256).hexdigest()
    return digest


def otp_expires_at(minutes: Optional[int] = None):
    mins = minutes if minutes is not None else getattr(settings, 'OTP_TTL_MINUTES', 10)
    return timezone.now() + timedelta(minutes=mins)

