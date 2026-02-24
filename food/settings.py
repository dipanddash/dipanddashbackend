from pathlib import Path
from datetime import timedelta
import os
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='dev-secret-key-change-later')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*').split(',')

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "corsheaders",
    "rest_framework",
    "foodbackend",  # 🔁 change this
]

DATABASES = {
    "default": {
        "ENGINE": config('DB_ENGINE', default='django.db.backends.postgresql'),
        "NAME": config('DB_NAME', default='neondb'),
        "USER": config('DB_USER', default='neondb_owner'),
        "PASSWORD": config('DB_PASSWORD', default='npg_5IOm9xLqBQMU'),
        "HOST": config('DB_HOST', default='ep-winter-sunset-ah66qvua-pooler.c-3.us-east-1.aws.neon.tech'),
        "PORT": config('DB_PORT', default='5432'),
        "OPTIONS": {
            "sslmode": "require",
        },
        "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", default=60, cast=int),
        "CONN_HEALTH_CHECKS": True,
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=6),   # ✅ 6 DAYS
    "REFRESH_TOKEN_LIFETIME": timedelta(days=6),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

# CSRF Configuration for React Frontend
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS', 
    default='http://localhost:3000,http://127.0.0.1:3000'
).split(',')
CSRF_COOKIE_HTTPONLY = False  # Allow JavaScript to access CSRF cookie
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)  # Set to True in production with HTTPS
CSRF_COOKIE_AGE = 31449600  # 1 year

# CORS Configuration
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS', 
    default='http://localhost:3000,http://127.0.0.1:3000'
).split(',')
CORS_ALLOW_CREDENTIALS = True  # Allow cookies to be sent
CORS_ALLOW_HEADERS = [
    "content-type",
    "x-csrftoken",
    "authorization",
]

# Session Configuration
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)  # Set to True in production with HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

ROOT_URLCONF = "food.urls"  # 🔁 change this
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

GOOGLE_GEOCODING_API_KEY = os.getenv("GOOGLE_GEOCODING_API_KEY", "")

# Fast2SMS (OTP)
FAST2SMS_API_KEY = "SVWlJ9CKauuX7gybb8ujMQVndV1GfJQdXU8birIJBrgDk3aGlItIQrckx47X"
FAST2SMS_SENDER_ID = "ASINTL"
FAST2SMS_ROUTE = "dlt"
FAST2SMS_TEMPLATE_ID = "209453"
FAST2SMS_MESSAGE_TEMPLATE = "Your OTP for login to Dip & Dash is {otp} . Do not share it with anyone. -Dip and Dash"

# OTP Development Mode (Set to True to bypass SMS and print OTP to console)
OTP_DEV_MODE = False
