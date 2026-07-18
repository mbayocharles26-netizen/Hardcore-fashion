import os
import ssl
import urllib.request
import urllib.error
import django

os.environ['DJANGO_SETTINGS_MODULE'] = 'ecommerce.settings'
django.setup()
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from store.models import AdminProfile

profile = AdminProfile.objects.select_related('user').filter(is_active=True).first()
if not profile:
    raise SystemExit('No active AdminProfile found')
user = profile.user
print('Admin user:', user.username, 'id', user.id)
refresh = RefreshToken.for_user(user)
access = str(refresh.access_token)
print('Generated access token length:', len(access))
ctx = ssl._create_unverified_context()
for path in ['/api/admin/dashboard/', '/api/admin/reports/']:
    url = 'https://127.0.0.1:8443' + path
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {access}'})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            print('URL', url, 'STATUS', r.status)
            body = r.read(8192)
            print(body.decode('utf-8', 'replace'))
    except urllib.error.HTTPError as e:
        print('URL', url, 'HTTP_ERROR', e.code)
        print(e.read(8192).decode('utf-8', 'replace'))
    except Exception as e:
        print('URL', url, 'EXCEPTION', type(e).__name__, e)
