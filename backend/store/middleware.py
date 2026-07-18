"""
SQL Injection Detection Middleware
Inspects incoming requests for known SQLi patterns in query params,
URL path, and JSON/form body. Logs and blocks suspicious requests.
"""
import json
import logging
import re

from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger('security')

# Patterns that are never legitimate in this application's inputs.
# Ordered from most specific to most general to minimise false positives.
_SQLI_PATTERNS = re.compile(
    r"""
    (\bOR\b\s+['"\d]+\s*=\s*['"\d]+)   # OR 1=1 / OR 'a'='a'
    | (\bAND\b\s+['"\d]+\s*=\s*['"\d]+) # AND 1=1
    | (--\s)                             # SQL line comment
    | (;\s*DROP\b)                       # ; DROP TABLE
    | (;\s*DELETE\b)                     # ; DELETE FROM
    | (;\s*INSERT\b)                     # ; INSERT INTO
    | (;\s*UPDATE\b)                     # ; UPDATE SET
    | (\bUNION\b.+\bSELECT\b)           # UNION SELECT
    | (\bEXEC\s*\()                      # EXEC(
    | (\bXP_\w+)                         # xp_cmdshell etc.
    | (/\*.*?\*/)                        # /* block comment */
    | (\bSLEEP\s*\()                     # SLEEP(
    | (\bBENCHMARK\s*\()                 # BENCHMARK(
    | (\bWAITFOR\b)                      # WAITFOR DELAY (MSSQL)
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

# Paths that are exempt from body inspection (binary uploads, etc.)
_EXEMPT_PREFIXES = ('/admin/', '/static/', '/media/')


def _check(value: str) -> bool:
    """Return True if the value contains a SQLi pattern."""
    return bool(_SQLI_PATTERNS.search(value))


def _extract_strings(data, depth=0):
    """Recursively yield all string values from a dict/list structure."""
    if depth > 8:
        return
    if isinstance(data, str):
        yield data
    elif isinstance(data, dict):
        for v in data.values():
            yield from _extract_strings(v, depth + 1)
    elif isinstance(data, list):
        for item in data:
            yield from _extract_strings(item, depth + 1)


class SqlInjectionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not any(request.path.startswith(p) for p in _EXEMPT_PREFIXES):
            threat = self._scan(request)
            if threat:
                logger.warning(
                    'SQLi attempt blocked | ip=%s method=%s path=%s match=%r',
                    self._ip(request),
                    request.method,
                    request.path,
                    threat,
                )
                return JsonResponse(
                    {'detail': 'Invalid input detected.'},
                    status=400,
                )
        return self.get_response(request)

    # ── Scanning helpers ──────────────────────────────────────────────────────

    def _scan(self, request):
        # 1. Query string parameters
        for value in request.GET.values():
            if _check(value):
                return value

        # 2. URL path itself
        if _check(request.path):
            return request.path

        # 3. Request body (JSON or form-encoded)
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            try:
                body = json.loads(request.body.decode('utf-8', errors='replace'))
                for s in _extract_strings(body):
                    if _check(s):
                        return s
            except (ValueError, UnicodeDecodeError):
                pass
        elif 'application/x-www-form-urlencoded' in content_type or 'multipart/form-data' in content_type:
            for value in request.POST.values():
                if _check(value):
                    return value

        return None

    @staticmethod
    def _ip(request):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


class PostgresRLSMiddleware:
    """Set PostgreSQL session variables so RLS policies can enforce current user context."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._set_rls_session(request)
        try:
            response = self.get_response(request)
        finally:
            self._reset_rls_session()
        return response

    def _set_rls_session(self, request):
        if connection.vendor != 'postgresql':
            return

        role = 'anonymous'
        user_id = 0
        vendor_id = 0

        if request.user.is_authenticated:
            user_id = request.user.id
            if getattr(request.user, 'is_superuser', False) or getattr(request.user, 'admin_profile', None):
                role = 'admin'
            elif getattr(request.user, 'vendor_profile', None):
                role = 'vendor'
                vendor_id = request.user.vendor_profile.id
            else:
                role = 'customer'

        with connection.cursor() as cursor:
            cursor.execute("SET \"app.current_user_id\" = %s", [user_id])
            cursor.execute("SET \"app.current_role\" = %s", [role])
            cursor.execute("SET \"app.current_vendor_id\" = %s", [vendor_id])

    def _reset_rls_session(self):
        if connection.vendor != 'postgresql':
            return
        with connection.cursor() as cursor:
            cursor.execute("SET \"app.current_user_id\" = 0")
            cursor.execute("SET \"app.current_role\" = 'anonymous'")
            cursor.execute("SET \"app.current_vendor_id\" = 0")
