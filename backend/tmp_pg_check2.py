import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ecommerce.settings")
import django
django.setup()
from django.db import connection
print('vendor', connection.vendor)
with connection.cursor() as cursor:
    for cmd in [
        'SET "app.current_role" = \'anonymous\'',
        'SHOW "app.current_role"',
        'SET "app.current_user_id" = 0',
        'SHOW "app.current_user_id"',
        'SET "app.current_vendor_id" = 0',
        'SHOW "app.current_vendor_id"',
    ]:
        try:
            cursor.execute(cmd)
            result = cursor.fetchone() if cursor.description else None
            print('OK', cmd, result)
        except Exception as e:
            print('ERR', cmd, type(e).__name__, e)
