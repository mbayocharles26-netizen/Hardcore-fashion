from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = (
        'Verify PostgreSQL RLS session variables for the current database connection. '
        'Useful to confirm app.current_user_id, app.current_role, and app.current_vendor_id are available.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            default=0,
            help='Test user id to set in the session.',
        )
        parser.add_argument(
            '--role',
            choices=['anonymous', 'customer', 'vendor', 'admin'],
            default='anonymous',
            help='Test role to set in the session.',
        )
        parser.add_argument(
            '--vendor-id',
            type=int,
            default=0,
            help='Test vendor id to set in the session.',
        )

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            self.stdout.write(self.style.WARNING('RLS session checks are PostgreSQL-only.'))
            self.stdout.write(f'Current database engine: {connection.vendor}')
            return

        user_id = options['user_id']
        role = options['role']
        vendor_id = options['vendor_id']

        try:
            with connection.cursor() as cursor:
                cursor.execute("SET \"app.current_user_id\" = %s", [user_id])
                cursor.execute("SET \"app.current_role\" = %s", [role])
                cursor.execute("SET \"app.current_vendor_id\" = %s", [vendor_id])
                cursor.execute("SHOW \"app.current_user_id\"")
                current_user_id = cursor.fetchone()[0]
                cursor.execute("SHOW \"app.current_role\"")
                current_role = cursor.fetchone()[0]
                cursor.execute("SHOW \"app.current_vendor_id\"")
                current_vendor_id = cursor.fetchone()[0]
        except Exception as exc:
            raise CommandError(f'PostgreSQL RLS session variable verification failed: {exc}')

        self.stdout.write(self.style.SUCCESS('PostgreSQL RLS session variable check passed.'))
        self.stdout.write(f'  app.current_user_id = {current_user_id}')
        self.stdout.write(f'  app.current_role = {current_role}')
        self.stdout.write(f'  app.current_vendor_id = {current_vendor_id}')
