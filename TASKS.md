# Delivery tasks

## Phase 0

- [x] Define system architecture and contracts
- [x] Define data model, API shape, and UI flow
- [x] Environment policy (backend `.env.example`, frontend `.env.local.example`)
- [x] Database migration baseline (Alembic async env + initial migration; startup runs `upgrade head`)
- [x] Error tracking (guarded Sentry backend init + frontend ErrorBoundary/observability)
- [x] CI pipeline (GitHub Actions: backend ruff+pytest+alembic check, frontend build)

## Phase 1

- [x] Build product shell and design primitives
- [x] Build landing page and demo report entry point
- [x] Build dashboard, analysis intake, live progress, and report viewer routes
- [x] Add client-side validation, navigation, loading, error, and responsive states
- [x] Verify visual and keyboard interaction quality

## Phase 2 — Exploration pipeline

- [x] FastAPI job API (create/get/cancel/events) with idempotency keys
- [x] In-process + Redis queue drivers and a standalone worker
- [x] Isolated Playwright exploration with SSRF policy, request budgets, screenshots
- [x] Lightweight HTTP fallback explorer when a browser binary is unavailable
- [x] Persist sanitized evidence and stream progress over SSE

## Phase 3 — Intelligence reports

- [x] Signature-based technology/integration detection over observable signals
- [x] Deterministic analyzer: architecture, flows, entities, API, insights, security
- [x] Model adapter (GPT-5 via httpx) with an offline deterministic fallback
- [x] Report + claim persistence with per-claim confidence and evidence
- [x] Reports list/detail, search, favorite, delete, JSON/Markdown export, stats
- [x] Full-stack wiring verified: analyze → live → report

## Phase 5 — Advanced intelligence (started)

- [x] Compare mode: structured two-report diff (tech, features, insights, architecture, confidence Δ) + `/compare` UI
- [ ] Architecture diff visualization and API behavior analysis
- [ ] Security posture deep-dive, Figma/GitHub inputs, system-design export

## Phase 4 — Team readiness

- [x] Real authentication (email + password, PBKDF2, bearer-token sessions)
- [x] Organizations, memberships, and per-tenant scoping of analyses + reports
- [x] Role-based access control (owner/admin can delete; audit log of actions)
- [x] Plan-based monthly analysis quotas (Free = 25) enforced on create
- [x] Frontend auth: login/signup, token storage, route guard, 401 handling
- [x] Settings usage meter, plan cards, and sign-out

## Phase 4 — Social sign-in

- [x] Google + GitHub OAuth 2.0 authorization-code flow (`services/oauth.py`)
- [x] `/auth/oauth/{provider}/start` + `/callback` with CSRF state and token-in-fragment handoff
- [x] Find-or-create user by verified email; passwordless OAuth accounts
- [x] Graceful "provider not configured" handling; providers activate via env creds
- [x] Frontend buttons wired + `#token`/`#error` callback handling on /login

## Phase 4/5 (next)

- [ ] Team invitations and multi-member organizations (model + endpoints exist)
- [ ] Report versioning and cursor-paginated infinite scroll in the UI
- [ ] Command palette (⌘K) for quick navigate/analyze
