FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    HF_HOME=/home/app/.cache/huggingface
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 curl && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# Bake the embedding model into the image so the stack works offline after the first build.
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RUN mkdir -p /home/app/.cache && /app/.venv/bin/python -c \
    "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')" \
    && chown -R app:app /home/app/.cache

COPY . .
RUN SECRET_KEY_BUILD=1 DJANGO_SECRET_KEY=build DJANGO_DEBUG=0 /app/.venv/bin/python manage.py collectstatic --noinput \
    && chown -R app:app /app/staticfiles
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "--access-logfile", "-"]
