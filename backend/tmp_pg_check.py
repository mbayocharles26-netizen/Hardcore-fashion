import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerce.settings')
import django
django.setup()
from django.db import connection
print('vendor', connection.vendor)
with connection.cursor() as cursor:
    cursor.execute('SELECT version()')
    print('version', cursor.fetchone()[0])
    try:
        cursor.execute("SET app.current_role = 'anonymous'")
        print('SET ok')
    except Exception as e:
        print('SET err', type(e).__name__, e)
    try:
        cursor.execute("SHOW app.current_role")
        print('SHOW ok', cursor.fetchone())
    except Exception as e:
        print('SHOW err', type(e).__name__, e)
