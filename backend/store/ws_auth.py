"""
JWT authentication middleware for Django Channels WebSocket connections.

Django's AuthMiddlewareStack only handles session-based auth. This middleware
reads a `token` query-string parameter, validates it as a SimpleJWT access
token, and populates scope['user'] so consumers can call is_authenticated.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser, User
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _get_user(token_str):
    try:
        token = AccessToken(token_str)
        return User.objects.select_related('vendor_profile').filter(
            id=token['user_id'], is_active=True
        ).first() or AnonymousUser()
    except (InvalidToken, TokenError, KeyError):
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        qs = parse_qs(scope.get('query_string', b'').decode())
        token_list = qs.get('token', [])
        if token_list:
            scope['user'] = await _get_user(token_list[0])
        elif scope.get('user') is None:
            scope['user'] = AnonymousUser()
        return await super().__call__(scope, receive, send)
