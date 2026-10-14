.DEFAULT_GOAL := help
COMPOSE ?= docker compose
BACKEND_DB_URL ?= postgres://contextforge:contextforge@127.0.0.1:55432/contextforge

help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

env: ## Create .env from the example with generated local secrets
	@./scripts/bootstrap-env.sh

corpus: ## Download the public demo corpus (RFCs, arXiv PDFs, Gutenberg, Rust book) into data/corpus
	./scripts/fetch_corpus.sh

seed: ## Create demo users/orgs/roles and upload the corpus through the API (stack must be up)
	./scripts/seed_demo.sh

creds: ## Print every local login (demo users + infra dashboards)
	@./scripts/show-credentials.sh

model: ## Download EMBEDDING_MODEL into data/hf-cache (alternative to rebuilding the image)
	cd backend && HF_HOME=$(CURDIR)/data/hf-cache uv run python -c "import os; from sentence_transformers import SentenceTransformer as S; S(os.environ.get('EMBEDDING_MODEL','intfloat/multilingual-e5-small'))"

up: ## Build and start the whole stack (http://localhost:8080)
	$(COMPOSE) up -d --build

down: ## Stop the stack (keeps volumes)
	$(COMPOSE) down

reset: ## Stop the stack and DELETE all data volumes
	$(COMPOSE) down -v

logs: ## Tail logs
	$(COMPOSE) logs -f --tail=100

ps: ## Service status
	$(COMPOSE) ps

migrate: ## Run migrations in the stack
	$(COMPOSE) run --rm init

reindex: ## Re-queue documents indexed with an outdated model/chunk config
	$(COMPOSE) exec worker python manage.py reindex_stale

test-db: ## Start a throwaway Postgres for backend tests on :55432
	@docker start cf-test-pg 2>/dev/null || docker run -d --name cf-test-pg -e POSTGRES_USER=contextforge -e POSTGRES_PASSWORD=contextforge -e POSTGRES_DB=contextforge -p 127.0.0.1:55432:5432 postgres:17-alpine
	@until docker exec cf-test-pg pg_isready -U contextforge >/dev/null 2>&1; do sleep 1; done

test-backend: test-db ## Backend tests (no external services besides Postgres; Gemini/S3/Qdrant are mocked)
	cd backend && DATABASE_URL=$(BACKEND_DB_URL) uv run pytest

lint-backend: ## Ruff lint + format check + mypy
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy apps

test-frontend: ## Frontend typecheck, lint, unit tests
	cd frontend && npm run typecheck && npm run lint && npm test

e2e: ## Playwright end-to-end (requires the stack to be up)
	cd frontend && npx playwright test

schema: ## Export OpenAPI schema to docs/openapi.yaml
	cd backend && DATABASE_URL=$(BACKEND_DB_URL) DJANGO_DEBUG=1 uv run python manage.py spectacular --file ../docs/openapi.yaml

check: lint-backend test-backend test-frontend ## Everything CI runs
