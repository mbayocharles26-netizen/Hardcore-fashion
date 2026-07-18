from __future__ import annotations

import functools

from django.contrib.auth.models import User
from django.http import HttpRequest
from django.shortcuts import render


def _has_admin_profile(user: User | None) -> bool:
    """True if the user has an active AdminProfile (custom website admin)."""
    if not user:
        return False
    profile = getattr(user, "admin_profile", None)
    return bool(profile and getattr(profile, "is_active", False))


def get_role(user: User | None) -> str:
    """Return one of: admin | vendor | customer."""
    if not user or not getattr(user, "is_authenticated", False):
        return "customer"

    if (
        getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
        or _has_admin_profile(user)
    ):
        return "admin"

    if getattr(user, "vendor_profile", None):
        return "vendor"

    return "customer"


def _has_admin_access(user: User | None) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return bool(
        getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
        or _has_admin_profile(user)
    )


def _has_vendor_access(user: User | None) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return bool(getattr(user, "vendor_profile", None))


def _has_customer_access(user: User | None) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return get_role(user) == "customer"


def require_role(*, role: str):
    """Decorator factory.

    Usage:
        @require_role(role="admin")
        def my_view(request):
            ...
    """

    def decorator(view_fn):
        @functools.wraps(view_fn)
        def _wrapped(request: HttpRequest, *args, **kwargs):
            user = getattr(request, "user", None)

            if role == "admin" and not _has_admin_access(user):
                return render(request, "403.html", status=403)
            if role == "vendor" and not _has_vendor_access(user):
                return render(request, "403.html", status=403)
            if role == "customer" and not _has_customer_access(user):
                return render(request, "403.html", status=403)

            return view_fn(request, *args, **kwargs)

        return _wrapped

    return decorator

