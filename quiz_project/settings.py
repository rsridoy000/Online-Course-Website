"""
Django settings for quiz_project project.
"""

from pathlib import Path
from datetime import timedelta
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-quiz-app-secret-key-change-in-production'

# Dynamically disable DEBUG on Vercel
DEBUG = not os.environ.get('VERCEL')

ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = [
    'https://online-course-website-omega.vercel.app',
    'https://*.vercel.app',
    'http://127.0.0.1',
    'http://localhost'
]

# Security settings for production
if os.environ.get('VERCEL') or not DEBUG:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_TRUSTED_ORIGINS += ['https://online-course-website-omega.vercel.app']
    CSRF_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Added for Vercel/Proxy support
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cloudinary',
    'axes',
    'quiz_app',
]

MIDDLEWARE = [
    'quiz_app.middleware.ExceptionLoggingMiddleware',  # <--- Catch exceptions for diagnostics
    'quiz_app.middleware.RemoveFingerprintingMiddleware',  # <--- Strips fingerprinting headers first
    'django.middleware.security.SecurityMiddleware',
    'csp.middleware.CSPMiddleware',  # <--- Content Security Policy middleware
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',  # <--- Brute force tracking middleware
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'quiz_app.middleware.UserActivityMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesBackend',  # Keep first to monitor login attempts
    'django.contrib.auth.backends.ModelBackend',
]

ROOT_URLCONF = 'quiz_project.urls'


# Use cached template loader in production for faster rendering
if DEBUG:
    TEMPLATES = [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [os.path.join(BASE_DIR, 'templates')],
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                    'quiz_app.context_processors.unread_notices_count',
                ],
            },
        },
    ]
else:
    TEMPLATES = [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [os.path.join(BASE_DIR, 'templates')],
            'APP_DIRS': False,
            'OPTIONS': {
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                    'quiz_app.context_processors.unread_notices_count',
                ],
                'loaders': [
                    ('django.template.loaders.cached.Loader', [
                        'django.template.loaders.filesystem.Loader',
                        'django.template.loaders.app_directories.Loader',
                    ]),
                ],
            },
        },
    ]

WSGI_APPLICATION = 'quiz_project.wsgi.application'

# Database configuration
# Conditionally use Neon PostgreSQL on Vercel (or if DATABASE_URL is set), and fallback to local SQLite for development.
# We check if psycopg2 and dj_database_url are installed first, so Django doesn't crash if they are missing.
try:
    import psycopg2
    has_psycopg2 = True
except ImportError:
    has_psycopg2 = False

try:
    import dj_database_url as _dj_database_url
    has_dj_database_url = True
except ImportError:
    has_dj_database_url = False

if (os.environ.get('VERCEL') or os.environ.get('DATABASE_URL')) and has_psycopg2 and has_dj_database_url:
    try:
        DATABASES = {
            'default': _dj_database_url.config(
                default='postgresql://neondb_owner:npg_cAtom0jXEY8y@ep-curly-tree-ao9i5ghm.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require',
                conn_max_age=0
            )
        }
    except Exception as e:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {
                'timeout': 20,
            }
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'   # ✅ Fixed: UTC থেকে Bangladesh time
USE_I18N = False  # Disable i18n for speed (not needed for Bengali/English fixed app)
USE_TZ = True
USE_L10N = False

DATE_FORMAT = 'd/m/Y'
DATETIME_FORMAT = 'd/m/Y H:i'
SHORT_DATE_FORMAT = 'd/m/Y'

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Cloudinary setup (Enforced in Production)
if os.environ.get('VERCEL') or not DEBUG:
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': 'dga82u1w1',
        'API_KEY': '286863492173943',
        'API_SECRET': 'aK11zRB-naqxysF-u6Kzk3GBr90',
    }
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'


# Added for larger profile image uploads
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Use cached_db session for speed: reads from memory cache, writes to DB
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_COOKIE_AGE = 86400
SESSION_SAVE_EVERY_REQUEST = False  # Only save session when data changes

LOGIN_URL = 'student_login'
LOGIN_REDIRECT_URL = 'home'

# Email Configuration
# On Vercel: set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD as Environment Variables
# Locally: falls back to hardcoded values below
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'itzabir437@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'qsswefaecqeadugl')
EMAIL_DEFAULT_FROM_EMAIL = f'Liquid Triple R <{EMAIL_HOST_USER}>'
EMAIL_TIMEOUT = 10

# ==================== SECURITY HEADERS & POLICIES ====================
# Content Security Policy (CSP) Settings
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'", "https://cdn.jsdelivr.net")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com", "https://cdnjs.cloudflare.com")
CSP_IMG_SRC = ("'self'", "data:", "https://res.cloudinary.com")
CSP_FRAME_SRC = ("'none'",)
CSP_FRAME_ANCESTORS = ("'self'",)
CSP_CONNECT_SRC = ("'self'",)

# Brute-Force Lockout (django-axes) Settings
AXES_FAILURE_LIMIT = 5                      # Lockout after 5 failed login attempts
AXES_COOLOFF_TIME = timedelta(hours=1)      # Lockout cooldown: 1 hour (must be timedelta in axes 6.x)
AXES_RESET_ON_SUCCESS = True                # Reset counter when login succeeds
# Tell django-axes to use our custom IP lookup function.
# This avoids django-ipware's strict proxy counting checks, which raised a SuspiciousOperation (HTTP 400 Bad Request) on Vercel.
AXES_CLIENT_IP_CALLABLE = 'quiz_app.ip_helper.get_client_ip'

