TODO notes for redirect fix:
- LOGIN_REDIRECT_URL now points to /redirect/
- Need to add login_redirect view to backend/store/views.py
- Need to expose /redirect/ route from backend/store/template_urls.py
- login_redirect should route admin->/admin/dashboard/, vendor->/vendor-dashboard/, customer->/customer-dashboard/
- Dashboards are already decorated with @require_role in template_urls.py
- Ensure dashboard_access require_role renders frontend/templates/403.html with status=403

