"""DOC: security#configuration"""
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.core.exceptions import ImproperlyConfigured
from .lan import lan_configuration

BASE_DIR = Path(__file__).resolve().parent.parent
DEN_ENV = os.environ.get('DEN_ENV', 'development')
if DEN_ENV not in ('development', 'staging', 'production', 'lan'):
    raise ImproperlyConfigured('Invalid DEN_ENV.')
PRODUCTION = DEN_ENV == 'production'
LAN = DEN_ENV == 'lan'
DEBUG = False
credentials = {}
if os.environ.get('DEN_SECRET_FILE'):
    try:
        secret_path = Path(os.environ['DEN_SECRET_FILE'])
        if DEN_ENV != 'development' and not secret_path.is_absolute():
            raise ValueError
        credentials = json.loads(secret_path.read_text(encoding='utf-8-sig'))
        if not isinstance(credentials, dict):
            raise ValueError
    except (OSError, ValueError):
        raise ImproperlyConfigured('Cannot load Den secrets.') from None
SECRET_KEY = credentials.get('django_secret', '')
if DEN_ENV != 'development' and (not isinstance(SECRET_KEY, str) or len(SECRET_KEY) < 50
        or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith('django-insecure-')):
    raise ImproperlyConfigured('A strong external Django secret is required.')
SECRET_KEY = SECRET_KEY or secrets.token_urlsafe(64)
DEN_PUBLIC_ORIGIN = os.environ.get('DEN_PUBLIC_ORIGIN', '')
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
CSRF_TRUSTED_ORIGINS = []
if PRODUCTION:
    try:
        origin = urlsplit(DEN_PUBLIC_ORIGIN)
        if (origin.scheme != 'https' or not origin.hostname or origin.username
                or origin.password or origin.path or origin.query or origin.fragment
                or origin.port not in (None, 443) or '*' in origin.netloc
                or DEN_PUBLIC_ORIGIN != 'https://' + origin.hostname):
            raise ValueError
    except ValueError:
        raise ImproperlyConfigured('DEN_PUBLIC_ORIGIN must be an exact HTTPS origin without a trailing slash.') from None
    ALLOWED_HOSTS = [origin.hostname]
    CSRF_TRUSTED_ORIGINS = [DEN_PUBLIC_ORIGIN]
DEN_LAN_ORIGIN = os.environ.get('DEN_LAN_ORIGIN', '')
DEN_LAN_SUBNET = os.environ.get('DEN_LAN_SUBNET', '')
DEN_LAN_HOST, DEN_LAN_PORT, DEN_LAN_NETWORK = None, None, None
if LAN or DEN_LAN_ORIGIN or DEN_LAN_SUBNET:
    try:
        DEN_LAN_HOST, DEN_LAN_PORT, DEN_LAN_NETWORK = lan_configuration(DEN_LAN_ORIGIN, DEN_LAN_SUBNET)
    except ValueError as exc:
        raise ImproperlyConfigured(str(exc)) from None
if LAN:
    ALLOWED_HOSTS = [DEN_LAN_HOST]
    CSRF_TRUSTED_ORIGINS = []
OPENROUTER_API_KEY = credentials.get('openrouter_api_key', '')
if DEN_ENV == 'development':
    OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', OPENROUTER_API_KEY)
if not isinstance(OPENROUTER_API_KEY, str):
    raise ImproperlyConfigured('Invalid provider credential configuration.')
DEN_AI_ENABLED = os.environ.get('DEN_AI_ENABLED', '0') == '1' and bool(OPENROUTER_API_KEY)
DEN_DEVICE_MAP_FILE = os.environ.get('DEN_DEVICE_MAP_FILE', '')
if DEN_DEVICE_MAP_FILE and not Path(DEN_DEVICE_MAP_FILE).is_absolute():
    raise ImproperlyConfigured('DEN_DEVICE_MAP_FILE must be absolute.')
DEN_DISPLAY_TIME_ZONE = os.environ.get('DEN_DISPLAY_TIME_ZONE', 'America/New_York')
try:
    ZoneInfo(DEN_DISPLAY_TIME_ZONE)
except (ZoneInfoNotFoundError, ValueError):
    raise ImproperlyConfigured('DEN_DISPLAY_TIME_ZONE must name an IANA time zone.') from None
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
                 'django.contrib.messages', 'django.contrib.staticfiles', 'myapp']
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'myapp.security.EnvelopeMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'myapp.security.WriteBudgetMiddleware',
]
if LAN:
    MIDDLEWARE.insert(0, 'myapp.security.LanBoundaryMiddleware')
ROOT_URLCONF = 'infonet.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'myapp' / 'templates'], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': ['django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'infonet.wsgi.application'
if DEN_ENV != 'development' and not Path(os.environ.get('DEN_DATA_DIR', '')).is_absolute():
    raise ImproperlyConfigured('An absolute DEN_DATA_DIR is required.')
DATA_DIR = Path(os.environ.get('DEN_DATA_DIR', str(BASE_DIR))).resolve()
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': DATA_DIR / 'db.sqlite3',
                       'OPTIONS': {'timeout': 5, 'transaction_mode': 'IMMEDIATE'}}}
if os.environ.get('DEN_TEST_DB') and DEN_ENV == 'development':
    DATABASES['default']['TEST'] = {'NAME': os.environ['DEN_TEST_DB']}
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
WHITENOISE_USE_FINDERS = DEN_ENV == 'development'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
DATA_UPLOAD_MAX_MEMORY_SIZE = 262144
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100
DATA_UPLOAD_MAX_NUMBER_FILES = 0
FILE_UPLOAD_MAX_MEMORY_SIZE = 0
SECURE_SSL_REDIRECT = PRODUCTION
SESSION_COOKIE_SECURE = PRODUCTION
CSRF_COOKIE_SECURE = PRODUCTION
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SAMESITE = 'Strict'
SECURE_HSTS_SECONDS = 31536000 if PRODUCTION else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
# DOC: security#configuration
SILENCED_SYSTEM_CHECKS = ['security.W005', 'security.W021']
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
USE_X_FORWARDED_HOST = False
SECURE_PROXY_SSL_HEADER = None
CSRF_FAILURE_VIEW = 'myapp.security.csrf_failure'
LOGGING = {'version': 1, 'disable_existing_loggers': True,
    'handlers': {'null': {'class': 'logging.NullHandler'}}, 'root': {'handlers': ['null']},
    'loggers': {name: {'handlers': ['null'], 'propagate': False}
                for name in ('django', 'waitress', 'httpx', 'httpcore')}}
