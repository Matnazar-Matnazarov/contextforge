# Worklog and Future Tasks

Use this file as the running project journal. Keep entries factual: what changed, what was verified, what remains.

## 2026-10-14 — Codex — Project Analysis and Build Hygiene

Goal: inspect the project, verify current health, and remove immediate build/check issues.

Files changed:

- `backend/apps/rag/vector_store.py`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/postcss.config.mjs`
- `docs/project-plan.md`
- `docs/worklog.md`
- `README.md`

Commands run:

- `make lint-backend` — passed.
- `DATABASE_URL=postgres://contextforge:contextforge@127.0.0.1:55432/contextforge uv run pytest` from `backend/` — 88 passed.
- `DATABASE_URL=postgres://contextforge:contextforge@127.0.0.1:55432/contextforge DJANGO_DEBUG=1 uv run python manage.py makemigrations --check --dry-run` from `backend/` — no changes detected.
- `make test-frontend` — passed.
- `npm run build` from `frontend/` — passed.
- `npm audit --omit=dev` from `frontend/` — 0 vulnerabilities.
- `npm audit --audit-level=high` from `frontend/` — dev-only high advisories through `eslint-config-next`; force fix would be breaking.

Notes:

- `make test-backend` initially failed because `127.0.0.1:55432` was already used by an existing `cf-pg` container while `cf-test-pg` was created but could not start. The stale `cf-test-pg` container was removed, and pytest was run directly against the existing local Postgres.
- Frontend build initially emitted an `@theme` parsing warning and did not compile Tailwind utility CSS correctly. Adding `@tailwindcss/postcss`, `postcss`, and `frontend/postcss.config.mjs` fixed the build output.

Next tasks:

- Run the full local browser flow through Caddy and record the result.
- Run Playwright E2E against the running stack.
- Review `.gitignore` before committing, because most repository files are currently untracked.
- Decide how to handle the dev-only `eslint-config-next` audit advisory without a breaking downgrade.

## Future Task Backlog

### High Priority

- Verify full Docker Compose runtime flow from registration through cited RAG answer.
- Run `make e2e` against the running stack and fix failures.
- Confirm document download authorization from the citation panel.
- Make backend test setup repeatable when another local Postgres already owns `127.0.0.1:55432`.

### Medium Priority

- Add a README "reviewer's path" for portfolio evaluators.
- Decide whether to export and commit `docs/openapi.yaml`.
- Review frontend empty, loading, failed upload, and failed indexing states manually in browser.
- Add or document an orphan-object cleanup strategy for upload-success/DB-failure edge cases.

### Low Priority

- Add optional screenshots or a local demo script using synthetic documents.
- Add more retrieval evaluation questions and fixture documents.
- Consider invitation flow for members who do not yet have accounts.
- Consider OCR support for scanned PDFs.

## 2026-10-14 — Claude — Demo corpus, role seed, browser verification

Goal: large realistic data in Postgres/SeaweedFS/Qdrant, logins per role, full browser testing.

Changes: `scripts/fetch_corpus.sh` (RFCs, arXiv PDFs, Gutenberg, Rust book → `data/corpus`, gitignored), `scripts/seed_demo.py|sh` (users, orgs, roles, uploads through the API),
`scripts/show-credentials.sh` (`make creds`), Django admin registrations, SeaweedFS filer/master UIs published on 127.0.0.1, Gemini fallback model + 4 attempts, new Playwright specs
(`roles`, `ui-actions`), `E2E_CHROMIUM` option in the Playwright config, README "Demo data and logins".

Findings: `gemini-2.5-flash` returned 404 "no longer available to new users" for the supplied key → default changed to `gemini-3.5-flash`; Google intermittently returns 503 "high demand" → retries + `GEMINI_FALLBACK_MODEL`.
Fixed an e2e race (`getByLabel("Name")` matched "Display name" on the register page before navigation).

Verified: seed indexed 42 docs (~11.7k vectors); `make lint-backend` clean; backend pytest 89 passed; frontend typecheck + eslint clean;
Playwright 14/14 passed against the running stack with system Chromium; Django admin login, Qdrant, RabbitMQ API and SeaweedFS filer responded.

## 2026-10-14 — Claude — Search, dashboard logins, model switch

- Added `GET /api/orgs/{id}/search/?q=` (tenant-scoped semantic passage search, no LLM) and a Search page in the UI; backend test + e2e test.
- Dashboard logins: Qdrant now requires `QDRANT_API_KEY` (dashboard asks for it); SeaweedFS filer UI is only reachable through Caddy basic auth on :8889 (`demo`/`Demo-Pass-2026!`); RabbitMQ and S3 use documented demo credentials written by `make env`.
- Gemini: `gemini-3.5-flash` hit free-tier quota (429); default now `gemini-3.5-flash-lite`, fallback `gemini-3-flash-preview`.
- Docker `npm ci` stalled on the default bridge network; building with `docker build --network host ./frontend` worked.
- Verified: backend pytest 90 passed, lint clean, frontend typecheck/eslint clean, Playwright 15/15, Qdrant 401 without key / 200 with key, filer 401 without / 200 with basic auth, S3 download via new keys.
