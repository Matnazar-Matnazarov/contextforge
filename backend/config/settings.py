"""Django settings. All configuration comes from environment variables."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, ["http://localhost:8080"]),
    DJANGO_CORS_ALLOWED_ORIGINS=(list, []),
    DJANGO_SECURE_COOKIES=(bool, False),
)

DEBUG = env("DJANGO_DEBUG")
SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-only-key" if DEBUG else None)
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "apps.core",
    "apps.accounts",
    "apps.organizations",
    "apps.documents",
    "apps.rag",
    "apps.chat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.RequestIdMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://contextforge:contextforge@localhost:5432/contextforge")
}
DATABASES["default"]["CONN_MAX_AGE"] = 60
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/django-static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Sessions / CSRF: same-origin via Caddy, so cookies are first-party. ---
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
# The SPA reads the CSRF cookie and echoes it in X-CSRFToken, so it cannot be HttpOnly.
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SECURE = env("DJANGO_SECURE_COOKIES")
CSRF_COOKIE_SECURE = env("DJANGO_SECURE_COOKIES")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# CORS is closed by default: the browser talks to a single origin (Caddy).
CORS_ALLOWED_ORIGINS = env("DJANGO_CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "auth": env("THROTTLE_AUTH", default="20/min"),
        "chat": env("THROTTLE_CHAT", default="20/min"),
        "upload": env("THROTTLE_UPLOAD", default="30/min"),
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "AI Knowledge Hub API",
    "DESCRIPTION": "Multi-tenant RAG platform. Session auth + CSRF; org scoped via /api/orgs/{org_id}/...",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# --- Celery / RabbitMQ ---
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="amqp://guest:guest@localhost:5672//")
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = env.int("CELERY_TASK_TIME_LIMIT", default=900)
CELERY_TASK_SOFT_TIME_LIMIT = env.int("CELERY_TASK_SOFT_TIME_LIMIT", default=840)
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# --- Object storage (SeaweedFS S3 API) ---
S3_ENDPOINT_URL = env("S3_ENDPOINT_URL", default="http://localhost:8333")
S3_BUCKET = env("S3_BUCKET", default="contextforge-documents")
S3_ACCESS_KEY = env("S3_ACCESS_KEY", default="")
S3_SECRET_KEY = env("S3_SECRET_KEY", default="")
S3_REGION = env("S3_REGION", default="us-east-1")

# --- Qdrant ---
QDRANT_URL = env("QDRANT_URL", default="http://localhost:6333")
QDRANT_API_KEY = env("QDRANT_API_KEY", default="") or None
QDRANT_COLLECTION = env("QDRANT_COLLECTION", default="knowledge_chunks")

# --- Embeddings ---
EMBEDDING_PROVIDER = env("EMBEDDING_PROVIDER", default="sentence_transformers")
EMBEDDING_MODEL = env("EMBEDDING_MODEL", default="sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIMENSIONS = env.int("EMBEDDING_DIMENSIONS", default=384)
EMBEDDING_BATCH_SIZE = env.int("EMBEDDING_BATCH_SIZE", default=32)

# --- Ingestion ---
MAX_UPLOAD_BYTES = env.int("MAX_UPLOAD_BYTES", default=10 * 1024 * 1024)
MAX_PDF_PAGES = env.int("MAX_PDF_PAGES", default=300)
CHUNK_SIZE = env.int("CHUNK_SIZE", default=1000)  # characters
CHUNK_OVERLAP = env.int("CHUNK_OVERLAP", default=150)
INDEX_MAX_RETRIES = env.int("INDEX_MAX_RETRIES", default=3)
# A document stuck in "processing" longer than this may be re-claimed (worker crash recovery).
PROCESSING_STALE_SECONDS = env.int("PROCESSING_STALE_SECONDS", default=1200)
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES + 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

# --- RAG / LLM ---
RAG_TOP_K = env.int("RAG_TOP_K", default=6)
RAG_SCORE_THRESHOLD = env.float("RAG_SCORE_THRESHOLD", default=0.30)
RAG_MAX_CONTEXT_CHARS = env.int("RAG_MAX_CONTEXT_CHARS", default=6000)
RAG_MAX_QUESTION_CHARS = env.int("RAG_MAX_QUESTION_CHARS", default=2000)
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")
GEMINI_MODEL = env("GEMINI_MODEL", default="gemini-3.5-flash-lite")
GEMINI_FALLBACK_MODEL = env("GEMINI_FALLBACK_MODEL", default="")  # tried once if the primary keeps failing
GEMINI_TIMEOUT_SECONDS = env.int("GEMINI_TIMEOUT_SECONDS", default=30)
GEMINI_MAX_ATTEMPTS = env.int("GEMINI_MAX_ATTEMPTS", default=4)
GEMINI_MAX_OUTPUT_TOKENS = env.int("GEMINI_MAX_OUTPUT_TOKENS", default=1024)

# --- Logging (structured, never logs bodies or secrets) ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}

AUTH_USER_MODEL = "accounts.User"
