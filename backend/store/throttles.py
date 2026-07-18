import logging

from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle

logger = logging.getLogger(__name__)


class LoggingRateThrottle(SimpleRateThrottle):
    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        if not allowed:
            self.log_throttle(request, view)
        return allowed

    def log_throttle(self, request, view):
        scope_name = getattr(self, 'scope', self.__class__.__name__)
        user = getattr(request, 'user', None)
        username = user.get_username() if getattr(user, 'is_authenticated', False) else 'anonymous'
        logger.warning(
            'Throttled request',
            extra={
                'scope': scope_name,
                'path': request.path,
                'method': request.method,
                'user': username,
                'remote_addr': self.get_ident(request),
            },
        )


class UserLoggingRateThrottle(LoggingRateThrottle, UserRateThrottle):
    scope = 'user'


class AnonLoggingRateThrottle(LoggingRateThrottle, AnonRateThrottle):
    scope = 'anon'


class LoginRateThrottle(AnonLoggingRateThrottle):
    scope = 'login'


class OtpRateThrottle(AnonLoggingRateThrottle):
    scope = 'otp'


class PaymentRateThrottle(UserLoggingRateThrottle):
    scope = 'payment'


class VendorRateThrottle(LoggingRateThrottle):
    scope = 'vendor'

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None

        vendor = getattr(request.user, 'vendor_profile', None)
        if vendor is None:
            return None

        return self.cache_format % {
            'scope': self.scope,
            'ident': f'vendor-{vendor.id}',
        }
