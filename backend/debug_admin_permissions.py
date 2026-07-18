import os
import django
os.environ['DJANGO_SETTINGS_MODULE'] = 'ecommerce.settings'
django.setup()
from store.admin_api import IsPlatformAdmin, AdminDashboardView
from store.models import AdminProfile
from django.test import RequestFactory
from django.contrib.auth.models import User

profile = AdminProfile.objects.select_related('user').first()
if not profile:
    raise SystemExit('No AdminProfile found')
user = profile.user
print('admin user:', user, 'is_active', user.is_active, 'username', user.username)
print('admin profile:', profile.role, profile.is_active)

req = RequestFactory().get('/')
req.user = user
permission = IsPlatformAdmin()
allowed = permission.has_permission(req, None)
print('permission has_permission:', allowed)
print('user.is_authenticated:', user.is_authenticated)

view = AdminDashboardView.as_view()
try:
    resp = view(req)
    print('view status_code:', resp.status_code)
    print('view data:', getattr(resp, 'data', None))
except Exception as exc:
    import traceback; traceback.print_exc()
