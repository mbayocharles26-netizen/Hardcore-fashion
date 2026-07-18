import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'ecommerce.settings'
django.setup()

from store.admin_api import AdminDashboardView, AdminReportsView
from store.models import AdminProfile
from django.test import RequestFactory
from django.contrib.auth.models import User

rf = RequestFactory()

# Find or create an admin user with AdminProfile
profile = AdminProfile.objects.select_related('user').first()
if not profile:
    print("No AdminProfile found. Creating one...")
    u = User.objects.filter(is_superuser=True).first() or User.objects.first()
    profile = AdminProfile.objects.create(user=u, role='super_admin', is_active=True)

u = profile.user
print("Admin user:", u, "role:", profile.role)

req = rf.get('/')
req.user = u

try:
    view = AdminDashboardView.as_view()
    resp = view(req)
    print("Dashboard status:", resp.status_code)
    if hasattr(resp, 'data'):
        print("Dashboard data keys:", list(resp.data.keys()) if resp.data else resp.data)
except Exception as e:
    import traceback; traceback.print_exc()

try:
    view2 = AdminReportsView.as_view()
    resp2 = view2(req)
    print("Reports status:", resp2.status_code)
except Exception as e:
    import traceback; traceback.print_exc()
