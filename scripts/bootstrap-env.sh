#!/usr/bin/env bash
# Creates .env from .env.example, replacing CHANGE_ME placeholders with random local secrets.
# GEMINI_API_KEY is left for you to fill in. Never overwrites an existing .env.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then echo ".env already exists; leaving it untouched."; exit 0; fi
rand() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "${1:-32}"; }
# Local-only dashboards get documented demo credentials (README); services are bound to 127.0.0.1.
# Never reuse them on a reachable host. Postgres and Django secrets stay random.
DEMO_PASSWORD='Demo-Pass-2026!'
sed \
  -e "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$(rand 64)|" \
  -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(rand 24)|" \
  -e "s|^RABBITMQ_PASSWORD=.*|RABBITMQ_PASSWORD=${DEMO_PASSWORD}|" \
  -e "s|^S3_ACCESS_KEY=.*|S3_ACCESS_KEY=demo-s3-access|" \
  -e "s|^S3_SECRET_KEY=.*|S3_SECRET_KEY=Demo-S3-Secret-2026|"
  -e "s|^QDRANT_API_KEY=.*|QDRANT_API_KEY=${DEMO_PASSWORD}|" \
  .env.example > .env
chmod 600 .env
echo "Created .env. Edit it and set GEMINI_API_KEY before asking questions."
