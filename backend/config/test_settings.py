from .settings import *  # noqa: F403

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-real-use"
EMBEDDING_PROVIDER = "hashing"
EMBEDDING_DIMENSIONS = 384
QDRANT_URL = ":memory:"
QDRANT_COLLECTION = "test_chunks"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
S3_BUCKET = "test-bucket"
S3_ENDPOINT_URL = ""
S3_ACCESS_KEY = "testing"
S3_SECRET_KEY = "testing"
GEMINI_API_KEY = ""
RAG_SCORE_THRESHOLD = 0.2
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {"auth": "1000/min", "chat": "1000/min", "upload": "1000/min"},
}
