Playwright end-to-end tests for the real stack.

    make up                      # stack must be running
    make seed                    # demo users/orgs/documents used by roles.spec.ts
    cd frontend && npx playwright install chromium     # or: export E2E_CHROMIUM=/usr/bin/chromium
    make e2e

Specs:

- `core-flow.spec.ts` — register, create org, upload, index, ask, cited answer; client-side file-type rejection.
- `roles.spec.ts` — owner/admin/member/outsider/multi-org permission matrix, tenant isolation, cited answers, insufficient-context answers (needs `make seed`).
- `ui-actions.spec.ts` — every button on a throwaway org: upload, download, re-index, delete, add member, change role, remove, chat, citation panel, delete conversation, sign out.

A valid `GEMINI_API_KEY`/`GEMINI_MODEL` is needed for cited answers; transient Google 503s can make chat tests slow (retries + fallback model).
