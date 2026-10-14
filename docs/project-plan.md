# Project Plan and Agent Handoff

This document is the shared execution plan for Codex, Claude, or any future agent working on AI Knowledge Hub.
Keep it current when priorities, verified status, or open risks change.

## Product Goal

AI Knowledge Hub is a local, portfolio-quality, multi-tenant RAG platform. Users authenticate, create or join
organizations, upload PDF/TXT/Markdown documents, wait for asynchronous indexing, and ask questions that are answered
from tenant-scoped retrieved passages with validated citations.

The project must stay focused on the core RAG, tenancy, security, and local-development story. Do not add billing,
remote deployment, unrelated analytics, Kubernetes, or extra services unless a specific requirement justifies it.

## Current Verified Status

Last verified: 2026-10-14.

| Area | Status | Evidence |
|---|---|---|
| Repository structure | Implemented | `backend/`, `frontend/`, `infra/`, `docs/`, `scripts/`, `docker-compose.yml`, `Makefile` exist. |
| Backend lint/type checks | Passing | `make lint-backend` passed. |
| Backend tests | Passing | `pytest` passed with 88 tests using the existing local Postgres on `127.0.0.1:55432`. |
| Migrations check | Passing | `python manage.py makemigrations --check --dry-run` reported no changes. |
| Frontend checks | Passing | `make test-frontend` passed: typecheck, ESLint, Vitest. |
| Frontend production build | Passing | `npm run build` passed after adding Tailwind PostCSS config. |
| Runtime audit | Clean | `npm audit --omit=dev` reported 0 vulnerabilities. |
| Dev audit | Known issue | `eslint-config-next` dependency chain reports high-severity dev-only advisories; forced fix would be breaking. |
| Full local stack | Verified | `make seed` + Playwright 14/14 (2026-10-14), see worklog. |

## Agent Operating Rules

- Inspect existing files before editing. Preserve user work and unrelated changes.
- Keep business logic out of views where practical; prefer services, adapters, and small testable modules.
- Treat multi-tenancy and authorization as backend responsibilities. Frontend hiding is never security.
- Never search Qdrant without a trusted organization filter constructed from server-side membership data.
- Never log secrets, document contents, full prompts, API keys, credentials, or stack traces to users.
- Use real checks. Do not claim tests, builds, Docker services, or user flows work unless verified.
- Prefer small, reviewable changes. Update this plan or `docs/worklog.md` when work changes project status.
- Keep all services local. Do not deploy remotely.

## Claude-Specific Brief

Claude should use this repository as the source of truth, not the original prompt alone. Before proposing new features,
read `README.md`, this file, `docs/architecture.md`, `docs/rag-pipeline.md`, and `docs/security.md`.

Claude's best contribution path:

1. Review for architecture, security, and product completeness.
2. Identify gaps against the Definition of Done.
3. Produce concise, file-specific recommendations or patches.
4. Avoid rewriting working foundations unless there is a clear bug, security issue, or maintainability win.
5. When reviewing, lead with risks and missing tests, then summarize.

Claude should not:

- Recommend Redis, hosted vector databases, billing, public deployment, or extra frameworks without a concrete need.
- Move authorization logic into the frontend.
- Replace the existing Django/DRF/Celery/Qdrant/SeaweedFS design with a new architecture.
- Mark the milestone complete until the full local user flow is verified.

## Codex-Specific Brief

Codex should continue implementing directly in the repository. Default to making the smallest safe change, then run the
relevant verification commands.

Before code edits:

1. Check `git status --short`.
2. Read the target files and nearby tests.
3. Announce the intended edit briefly.
4. Use `apply_patch` for manual edits.

After code edits:

1. Run focused tests first.
2. Run broader checks if the change touches shared behavior.
3. Update `docs/worklog.md` with actual commands and results.
4. Mention any skipped checks and why.

## Remaining Roadmap

### Phase A — Clean Handoff State

Goal: make the repository easy for another developer or agent to resume.

- Keep `docs/project-plan.md` and `docs/worklog.md` current.
- Review `.gitignore` so generated artifacts such as `.next/`, caches, local env files, and virtualenvs are ignored.
- Decide when to make the first clean commit, because most project files are currently untracked.
- Document the existing `cf-pg` / `cf-test-pg` port collision and choose one repeatable backend-test path.

### Phase B — Full Local Runtime Verification

Goal: prove the README quick-start works from services, not only tests.

- Run `make up` from a clean-ish state.
- Confirm `make ps` shows healthy services.
- Open `http://localhost:8080`.
- Register a user.
- Create an organization.
- Upload one synthetic fixture document.
- Wait until status is `Indexed`.
- Ask a question that should cite the uploaded document.
- Ask an unrelated question and confirm insufficient-context behavior.
- Confirm source citation panel/download authorization works.
- Record exact results in `docs/worklog.md`.

### Phase C — Portfolio Polish

Goal: make the public repository easier to evaluate quickly.

- Add screenshots or a short demo script if desired, using synthetic data only.
- Add a compact "reviewer's path" to README: fastest way to evaluate architecture, tests, and core flow.
- Ensure OpenAPI export command works and decide whether `docs/openapi.yaml` should be generated or ignored.
- Review frontend empty/error states in the running browser, not only tests.
- Run Playwright `make e2e` against the running stack and fix any failures.

### Phase D — Security and Reliability Review

Goal: close gaps that matter for a serious local portfolio app.

- Re-check CSRF/session cookie behavior through Caddy.
- Verify unauthorized cross-tenant document download attempts manually or through E2E.
- Review upload limits across Caddy, Django settings, and validation code.
- Review failure paths: broker down, object missing, Qdrant unavailable, Gemini unavailable.
- Decide whether to add an object-storage orphan sweep management command.
- Confirm logs do not include document text, prompts, credentials, or secrets.

### Phase E — Optional Future Improvements

Only do these after the core milestone is verified:

- Hybrid retrieval or reranking if retrieval fixtures show a real quality gap.
- Streaming answers if the UX needs it.
- Invitation flow for adding not-yet-registered users.
- Admin audit log for membership/document actions.
- OCR support for scanned PDFs.
- More realistic fixture corpus and retrieval evaluations.

## Definition of Done for Initial Milestone

The milestone is complete only when all items below are true and recorded in `docs/worklog.md`:

- Local services start successfully through Docker Compose.
- Migrations run successfully.
- A user can register or log in.
- A user can create/select an organization.
- An authorized user can upload a supported document.
- The document is stored in SeaweedFS.
- Celery indexes it asynchronously.
- Chunks are stored in Qdrant with the correct organization filter metadata.
- The frontend chat can ask a question and receive a Gemini answer from retrieved context.
- Citations are structured and validated against the current retrieval set.
- Unsupported questions produce an insufficient-context answer.
- Cross-tenant isolation tests pass.
- Backend lint, backend tests, frontend checks, and frontend build pass.
- README instructions are sufficient for a new developer to reproduce the setup.

## Update Protocol

When future work is done, update `docs/worklog.md` with:

- Date and agent.
- Goal.
- Files changed.
- Commands run.
- Actual results.
- Remaining risks or next actions.

If the roadmap changes materially, update this file in the same change.
