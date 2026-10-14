#!/usr/bin/env bash
# Prints local logins. Infra secrets are read from .env (random per machine, never committed).
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
P=${APP_PORT:-8080}
cat <<TXT
== App (http://localhost:$P)  password for all demo users: Demo-Pass-2026!
  owner@acme.test      owner  Acme Engineering
  admin@acme.test      admin  Acme Engineering, Globex Library
  member@acme.test     member Acme Engineering, Initech Docs
  owner@globex.test    owner  Globex Library
  multi@demo.test      owner Initech Docs | admin Globex Library | member Acme Engineering
  owner@uz.test        owner  Oʻzbek Bilim Bazasi (Uzbek Wikipedia articles)
  outsider@demo.test   no organization (isolation checks)
== Django admin (http://localhost:$P/django-admin/)
  admin@contextforge.test / Demo-Pass-2026!   (superuser)
== RabbitMQ management (http://localhost:15672)
  $RABBITMQ_USER / $RABBITMQ_PASSWORD
== SeaweedFS
  Filer UI (bucket browser): http://localhost:8889/buckets/$S3_BUCKET/   login: demo / Demo-Pass-2026!
  S3 endpoint:               http://localhost:8333  access key: $S3_ACCESS_KEY  secret: $S3_SECRET_KEY  bucket: $S3_BUCKET
== Qdrant dashboard (http://localhost:6333/dashboard)  enter API key: $QDRANT_API_KEY   collection: $QDRANT_COLLECTION
== PostgreSQL (not published): docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB
TXT
