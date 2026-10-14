#!/usr/bin/env bash
# Creates .env from .env.example, replacing CHANGE_ME placeholders with random local secrets.
# GEMINI_API_KEY is left for you to fill in. Never overwrites an existing .env.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then echo ".env already exists; leaving it untouched."; exit 0; fi
rand() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "${1:-32}"; }
sed \
  -e "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$(rand 64)|" \
  -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(rand 24)|" \
  -e "s|^RABBITMQ_PASSWORD=.*|RABBITMQ_PASSWORD=$(rand 24)|" \
  -e "s|^S3_ACCESS_KEY=.*|S3_ACCESS_KEY=$(rand 20)|" \
  -e "s|^S3_SECRET_KEY=.*|S3_SECRET_KEY=$(rand 40)|" \
  .env.example > .env
chmod 600 .env
echo "Created .env. Edit it and set GEMINI_API_KEY before asking questions."
