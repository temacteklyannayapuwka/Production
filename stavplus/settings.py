"""Django settings for the StavPlus project."""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def load_environment_file(path: Path) -> None:
    """Load local deployment variables without adding secrets to source control."""
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


load_environment_file(BASE_DIR / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError('DJANGO_SECRET_KEY must be configured in the environment.')

DEBUG = os.getenv('DJANGO_DEBUG', 'false').lower() in {'1', 'true', 'yes'}
ALLOWED_HOSTS = [host.strip() for host in os.getenv(
    'DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,stavplus.ru,www.stavplus.ru'
).split(',') if host.strip()]

INSTALLED_APPS = [
    'unfold',
    'unfold.contrib.filters',
    'unfold.contrib.forms',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'ckeditor',
    'ckeditor_uploader',
    'news',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'stavplus.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]
WSGI_APPLICATION = 'stavplus.wsgi.application'
ASGI_APPLICATION = 'stavplus.asgi.application'

DB_ENGINE = os.getenv('DB_ENGINE', 'django.db.backends.sqlite3')
DB_NAME = os.getenv('DB_NAME') or (
    BASE_DIR / 'db.sqlite3' if DB_ENGINE == 'django.db.backends.sqlite3' else ''
)

DATABASES = {
    'default': {
        'ENGINE': DB_ENGINE,
        'NAME': DB_NAME,
        'USER': os.getenv('DB_USER', ''),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

CORS_ALLOW_ALL_ORIGINS = True
CSRF_TRUSTED_ORIGINS = ['https://*.stavplus.ru']
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True
DATE_FORMAT = 'Y-m-d'
DATETIME_FORMAT = 'Y-m-d H:i:s'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_SAVE_EVERY_REQUEST = True

CKEDITOR_UPLOAD_PATH = 'uploads/'
CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': [
            ['Format', 'Styles'],
            ['Bold', 'Italic', 'Underline', 'Strike', 'RemoveFormat'],
            ['NumberedList', 'BulletedList', 'Outdent', 'Indent', 'Blockquote'],
            ['Link', 'Unlink', 'Image', 'Table', 'HorizontalRule', 'SpecialChar'],
            ['Undo', 'Redo', 'Source', 'Maximize'],
        ],
        'height': 520,
        'width': '100%',
        'resize_enabled': True,
        'removePlugins': 'elementspath',
    },
}

# Editorial admin is intentionally neutral: content should remain the focus.
UNFOLD = {
    'SITE_HEADER': 'Ставрополь+',
    'SITE_TITLE': 'Ставрополь+ · редакция',
    'SITE_SUBHEADER': 'Новости и материалы',
    'STYLES': ['/static/admin-symbols.css', '/static/admin-editorial.css?v=5'],
    'COLORS': {
        'primary': {
            '50': '#f7f7f6',
            '100': '#ecece7',
            '200': '#dbdbd5',
            '300': '#b9b9b1',
            '400': '#878780',
            '500': '#5d5d57',
            '600': '#373737',
            '700': '#2a2a2a',
            '800': '#202020',
            '900': '#151515',
            '950': '#0d0d0d',
        },
    },
}
