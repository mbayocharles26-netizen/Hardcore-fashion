# TODO

## Redirect fix: login should not send admins to Django default /admin/
- [x] Update `backend/ecommerce/settings.py` to set `LOGIN_REDIRECT_URL = '/redirect/'`.
- [x] Add `login_redirect` view in `backend/store/views.py`.
- [x] Wire `path('redirect/', login_redirect, ...)` into `backend/store/template_urls.py`.
- [ ] Ensure `/admin/dashboard/`, `/vendor-dashboard/`, `/customer-dashboard/` return 403 for wrong roles (templates already guarded via `@require_role`).
- [ ] Run server and verify login redirect for admin/vendor/customer.

