from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from store.models import AdminProfile


class Command(BaseCommand):
    help = 'Create the custom website admin account (not Django admin)'

    def handle(self, *args, **options):
        email = 'mbayocharles26@gmail.com'
        username = 'website_admin'
        password = 'XYZfrank@#231'

        if User.objects.filter(email__iexact=email).exists():
            self.stdout.write(self.style.WARNING(f'User with email {email} already exists. Skipping.'))
            return

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )
        user.is_staff = False
        user.is_superuser = False
        user.save()

        AdminProfile.objects.create(
            user=user,
            role=AdminProfile.ROLE_SUPER_ADMIN,
            is_active=True,
        )

        self.stdout.write(self.style.SUCCESS(
            f'Website admin created: username="{username}" email="{email}"'
        ))
