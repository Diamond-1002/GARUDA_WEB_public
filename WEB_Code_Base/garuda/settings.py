import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "local-development-only-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if host.strip()]

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework", "channels", "dashboard",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "garuda.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request", "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "garuda.wsgi.application"
ASGI_APPLICATION = "garuda.asgi.application"

def database_config(url):
    parsed = urlparse(url)
    if parsed.scheme in ("postgres", "postgresql"):
        return {"ENGINE": "django.db.backends.postgresql", "NAME": unquote(parsed.path.lstrip("/")),
                "USER": unquote(parsed.username or ""), "PASSWORD": unquote(parsed.password or ""),
                "HOST": parsed.hostname or "", "PORT": parsed.port or "5432",
                "CONN_MAX_AGE": 60}
    if parsed.scheme == "sqlite":
        name = unquote(parsed.path.lstrip("/")) or "db.sqlite3"
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / name}
    raise ValueError("DATABASE_URL must use sqlite:/// or postgresql://")

DATABASES = {"default": database_config(os.getenv("DATABASE_URL", "sqlite:///db.sqlite3"))}
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

MQTT = {
    "HOST": os.getenv("MQTT_HOST", "127.0.0.1"), "PORT": int(os.getenv("MQTT_PORT", "1883")),
    "USERNAME": os.getenv("MQTT_USERNAME", ""), "PASSWORD": os.getenv("MQTT_PASSWORD", ""),
    "CLIENT_ID": os.getenv("MQTT_CLIENT_ID", "garuda_django_backend"),
    "KEEPALIVE": int(os.getenv("MQTT_KEEPALIVE", "30")),
}
DEVICE_OFFLINE_SECONDS = int(os.getenv("DEVICE_OFFLINE_SECONDS", "30"))

