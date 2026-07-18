from django.contrib.auth.models import User
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

_AUTH_ERROR = AuthenticationFailed({
    'detail': 'No active account found with the given credentials.',
    'code': 'no_active_account',
})


def get_user_from_jwt_cookie_or_header(request):
    # 1. Try Authorization header (API calls)
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    raw_token = None
    if auth_header.startswith('Bearer '):
        raw_token = auth_header.split(' ', 1)[1].strip()
    # 2. Fall back to cookie (browser page navigations)
    if not raw_token:
        raw_token = request.COOKIES.get('access_token', '').strip()
    if not raw_token:
        return None
    try:
        token = AccessToken(raw_token)
        user_id = token['user_id']
        return User.objects.filter(id=user_id, is_active=True).first()
    except (InvalidToken, TokenError, KeyError):
        return None


def _get_user_role(user) -> str:
    """Return role string for JWT payload."""
    if getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False):
        return 'admin'
    profile = getattr(user, 'admin_profile', None)
    if profile and getattr(profile, 'is_active', False):
        return 'admin'
    if getattr(user, 'vendor_profile', None):
        return 'vendor'
    return 'customer'


class UsernameOrEmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Allow login with username OR email address."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = _get_user_role(user)
        return token

    def validate(self, attrs):
        username_or_email = (attrs.get('username') or '').strip()
        password = attrs.get('password') or ''

        if not username_or_email or not password:
            raise _AUTH_ERROR

        if '@' in username_or_email:
            user = User.objects.filter(email__iexact=username_or_email, is_active=True).first()
        else:
            user = User.objects.filter(username__iexact=username_or_email, is_active=True).first()

        if user is None or not user.check_password(password):
            raise _AUTH_ERROR

        attrs['username'] = user.get_username()
        data = super().validate(attrs)
        data['role'] = _get_user_role(user)
        return data
