from decouple import Config, RepositoryEnv, AutoConfig
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
# On Render, rootDir is backend/ so the project root IS the backend dir
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_FRONTEND_STATIC = _BACKEND_DIR.parent / 'frontend' / 'static'
_FRONTEND_TEMPLATES = _BACKEND_DIR.parent / 'frontend' / 'templates'
# Look for .env next to manage.py (backend/) first, then project root
_ENV_PATH = _BACKEND_DIR / '.env'
if not _ENV_PATH.exists():
    _ENV_PATH = BASE_DIR / '.env'
config = Config(RepositoryEnv(str(_ENV_PATH))) if _ENV_PATH.exists() else AutoConfig()

import os
SECRET_KEY = os.environ.get('SECRET_KEY', config('SECRET_KEY', default='django-insecure-change-me-in-production'))
DEBUG = os.environ.get('DJANGO_DEBUG', str(config('DJANGO_DEBUG', default=True))).lower() not in ('false', '0', 'no')
_allowed = os.environ.get('ALLOWED_HOSTS', config('ALLOWED_HOSTS', default='*'))
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(',')]
if 'hardcore-fashion.onrender.com' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('hardcore-fashion.onrender.com')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'store',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'store.middleware.PostgresRLSMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ecommerce.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [_FRONTEND_TEMPLATES],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]

import dj_database_url
_db_url = os.environ.get('DATABASE_URL', config('DATABASE_URL', default=''))
if _db_url:
    _db_config = dj_database_url.parse(_db_url, conn_max_age=600)
    # Only require SSL for external/production connections, not internal ones
    if not any(h in _db_url for h in ['localhost', '127.0.0.1', 'internal']):
        _db_config.setdefault('OPTIONS', {})['sslmode'] = 'require'
    DATABASES = {'default': _db_config}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='hardcore_fashion'),
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='127.0.0.1'),
            'PORT': config('DB_PORT', default='5432'),
        }
    }

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'store.throttles.UserLoggingRateThrottle',
        'store.throttles.AnonLoggingRateThrottle',
    ],
   'DEFAULT_THROTTLE_RATES': {
    'user': '1000/hour',
    'anon': '200/hour',
    'login': '50/hour',
    'otp': '50/hour',
    'payment': '100/hour',
    'vendor': '1000/hour',
}

}

STATIC_URL = '/static/'
STATICFILES_DIRS = [d for d in [_FRONTEND_STATIC] if d.exists()]
STATIC_ROOT = _BACKEND_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = _BACKEND_DIR / 'media'

CORS_ALLOW_ALL_ORIGINS = DEBUG
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/redirect/'

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ─────────────────────────────────────────────────────────────
# Email (SMTP) — configure via env/.env
#
# Required when running OTP/email features:
# EMAIL_HOST
# EMAIL_PORT (default 587)
# EMAIL_HOST_USER
# EMAIL_HOST_PASSWORD
# EMAIL_USE_TLS (default True)
# EMAIL_FROM_NAME (default 'Gmail')
# EMAIL_FROM_ADDRESS (default 'paynedabanica1@gmail.com')
# ─────────────────────────────────────────────────────────────

# Email (SMTP) configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com', cast=str)
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='', cast=str)
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='', cast=str)

# Sender identity
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
EMAIL_FROM_ADDRESS = config('EMAIL_FROM_ADDRESS', default=EMAIL_HOST_USER)

# OTP
OTP_TTL_MINUTES = config('OTP_TTL_MINUTES', default=10, cast=int)
OTP_HASH_SECRET = config('OTP_HASH_SECRET', default='dev-otp-secret-change-me', cast=str)

# ─────────────────────────────────────────────────────────────
# Flutterwave
# Configure via env/.env
#
# FLUTTERWAVE_PUBLIC_KEY
# FLUTTERWAVE_SECRET_KEY
# FLUTTERWAVE_ENV (test|live)
# ─────────────────────────────────────────────────────────────

FLUTTERWAVE_PUBLIC_KEY = config('FLUTTERWAVE_PUBLIC_KEY', default='', cast=str)
FLUTTERWAVE_SECRET_KEY = config('FLUTTERWAVE_SECRET_KEY', default='', cast=str)
FLUTTERWAVE_ENV = config('FLUTTERWAVE_ENV', default='test', cast=str)

# ─────────────────────────────────────────────────────────────
# Django Channels
# Uses Redis in production (set REDIS_URL in .env).
# Falls back to in-memory layer for local dev without Redis.
# ─────────────────────────────────────────────────────────────
ASGI_APPLICATION = 'ecommerce.asgi.application'

_redis_url = config('REDIS_URL', default='')
if _redis_url:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [_redis_url]},
        }
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        }
    }