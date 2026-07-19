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


def send_tracking_email(*, to_email: str, customer_name: str, order_id: int,
                        tracking_number: str, track_url: str) -> None:
    if not settings.DEFAULT_FROM_EMAIL:
        return
    subject = f'Your Hardcore Fashion Order #{order_id} Has Shipped!'
    message = (
        f'Hi {customer_name},\n\n'
        f'Great news — your order #{order_id} is on its way!\n\n'
        f'Tracking Code: {tracking_number}\n'
        f'Track your shipment here: {track_url}\n\n'
        f'Thank you for shopping with Hardcore Fashion Store.'
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [to_email], fail_silently=True)
