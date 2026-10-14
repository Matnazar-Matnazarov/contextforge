#!/usr/bin/env bash
# Fetch corpus (if needed), create the Django superuser, then seed users/orgs/documents via the API.
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/fetch_corpus.sh
docker compose exec -T api python manage.py shell -c "
from apps.accounts.models import User
u, _ = User.objects.get_or_create(email='admin@contextforge.test', defaults=dict(display_name='Django Superuser'))
u.is_staff = u.is_superuser = True; u.set_password('Demo-Pass-2026!'); u.save()
print('superuser admin@contextforge.test ready')"
python3 scripts/seed_demo.py "$@"
