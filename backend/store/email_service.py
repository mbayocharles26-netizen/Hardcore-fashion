from django.conf import settings
from django.core.mail import send_mail


def send_otp_email(*, to_email: str, otp_code: str, subject: str = 'Your OTP Code') -> None:
    if not settings.DEFAULT_FROM_EMAIL:
        raise RuntimeError('DEFAULT_FROM_EMAIL is not configured for sending OTP emails.')

    message = f'Your one-time password is: {otp_code}\n\nPlease do not share this code with anyone.'
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [to_email],
        fail_silently=False,
    )
