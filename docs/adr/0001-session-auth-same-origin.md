# ADR 0001: Session authentication behind a same-origin proxy

**Status:** accepted

**Context:** The browser app needs authentication without exposing long-lived tokens to JavaScript.

**Decision:** Use Django session cookies (HttpOnly) with CSRF protection. Caddy serves Next.js and Django from one origin, so cookies are first-party and CORS is not needed.

**Consequences:** Simple and safe by default; non-browser API clients must use the cookie+CSRF flow. Cross-origin deployment would need CORS/CSRF reconfiguration.
