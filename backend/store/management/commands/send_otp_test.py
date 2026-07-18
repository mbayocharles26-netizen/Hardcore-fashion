from django.core.management.base import BaseCommand

from store.email_service import send_otp_email


class Command(BaseCommand):
    help = 'Send a test OTP email using the Django email backend.'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Destination email address')
        parser.add_argument(
            '--otp',
            type=str,
            default=None,
            help='OTP value to send (default: random 6-digit code)',
        )

    def handle(self, *args, **options):
        email = options['email']
        otp = options['otp']

        if otp is None:
            from random import randint
            otp = f'{randint(100000, 999999)}'

        try:
            send_otp_email(to_email=email, otp_code=otp, subject='Test OTP Code')
            self.stdout.write(self.style.SUCCESS(f'Successfully sent OTP {otp} to {email}'))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'Failed to send OTP: {exc}'))
            raise
