# Orbit — AI Software Intelligence Platform

Orbit helps people understand how public software products work from the
outside. Give it a public SaaS URL and it explores the visible experience,
collects technical signals, and produces an evidence-backed engineering report.

This project combines a polished Next.js product interface with a FastAPI
analysis service. It is designed for product research, technical discovery,
competitive analysis, and learning from real software systems — without
pretending to have access to private source code or infrastructure.

## What I built

- A multi-page SaaS experience: landing page, dashboard, URL analysis flow,
  live progress view, and interactive report.
- A FastAPI backend that manages analyses, events, reports, authentication,
  database migrations, and background work.
- A controlled Playwright-based browser explorer with URL safety checks.
- Detection for frameworks, hosting, CDN, analytics, authentication, payments,
  CMS/commerce, experiments, APIs, DNS/email posture, and more.
- Evidence-aware reports: each conclusion can show the observed signal,
  reasoning, and confidence level; uncertain findings are marked accordingly.
- Performance, security, privacy, SEO, accessibility, and infrastructure
  checks based on externally observable data.
- Side-by-side report comparison and a structured 18-section report model.
- **Orbit Workflow Lab** compiles a discovered journey into a versioned,
  evidence-linked workflow contract with correlated API operations, explicit
  automation blockers, and downloadable Playwright and JSON artifacts.
- Authorized workflow capture imports a Chrome DevTools Recorder JSON export
  plus an optional matching HAR. Orbit retains action order and stable selectors
  while removing typed values, cookies, query strings, and request bodies locally.
- Saved workflows are persisted as versioned contracts and can be replayed in an
  isolated browser. Orbit records a redacted per-step run ledger, surfaces the
  first failure, and proposes selector repairs that require explicit approval.
- Manual, daily, and weekly monitors share the same replay engine. Scheduled
  runs are protected by `CRON_SECRET`. Required inputs can be kept in a
  tenant-scoped, write-only AES-256-GCM vault and are decrypted only inside the
  isolated runner. Failed runs can notify an encrypted Slack webhook or email
  destination without including captured inputs or page content.

## What Orbit can report

- **Architecture and tech stack** — browser-to-backend request flow, visible
  frameworks, vendors, hosting, CDN, and infrastructure signals.
- **Product intelligence** — features, user flows, data entities, permissions,
  and integrations inferred from public surfaces.
- **Security and privacy** — response headers, TLS details, trackers, cookie
  handling, consent tooling, and public security metadata.
- **Performance and SEO** — bundle weight, caching, compression, transport,
  metadata, structured data, robots rules, and sitemap signals.
- **Domain and API discovery** — DNS, email configuration, `security.txt`,
  OpenAPI, GraphQL, and native-app association-file checks.
- **Executable workflow intelligence** — turn a supported journey into a
  behavior trace, operation map, evidence ledger, and automation starter
  without presenting inferred selectors or payloads as observed facts.
- **Client code** — Orbit reads the public JavaScript bundles every visitor
  downloads (it never executes them) and reports the API endpoints, GraphQL
  operations, client routes, feature-flag keys, realtime channels, and
  libraries they reference. When a source map is publicly reachable, it
  reports the original file structure and npm dependencies, never the source
  text. Credential-shaped strings are flagged masked; values are never stored.
- **Observed data shapes** — HAR imports now carry the field names and types of
  JSON request and response bodies (`items[].title:string`). The browser
  computes these before upload and discards every value; the server re-checks
  them. Entities built from these shapes are marked observed, not conventional.

Orbit distinguishes observed facts from reasoned inferences. When public
evidence is insufficient, the report says so rather than guessing.

## Tech stack

| Area | Technology |
| --- | --- |
| Frontend | Next.js 15, React 19, TypeScript, TanStack Query, Framer Motion |
| Backend | FastAPI, SQLAlchemy, Alembic, PostgreSQL/SQLite |
| Analysis | Playwright with a safe HTTP fallback explorer |
| AI layer | Optional OpenAI-compatible model for report prose; deterministic analysis also works without an API key |

## Run it locally

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate # macOS/Linux
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

The API runs at `http://localhost:8000`.

### Frontend

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

To run backend tests:

```bash
cd backend
pytest
```

### Use Orbit from an AI agent (MCP)

Orbit ships an MCP server so agents such as Claude Code, Cursor, and Codex can
analyze products and query reports. It is a thin client of the HTTP API, so
analyses keep the backend's URL-safety checks, quotas, and tenancy.

```bash
cd backend
pip install -e ".[mcp]"
claude mcp add orbit -e ORBIT_API_URL=http://localhost:8000 -e ORBIT_API_TOKEN=<token> -- orbit-mcp
```

`ORBIT_API_TOKEN` is an Orbit session token; omit it when the backend runs with
auth disabled. Tools: `analyze_url`, `get_analysis`, `list_reports`,
`get_report` (pass `section`, such as `code_intel` or `api`, for full detail),
`ask_report`, and `compare_reports`.

## Notes

Authentication is disabled by default for local development. Production and
staging builds are protected by default; set `ORBIT_AUTH_DISABLED=true` and
`NEXT_PUBLIC_AUTH_DISABLED=true` only when intentionally publishing a shared demo.

Production replay requires `ORBIT_CAPTURE_SECRET` and the serverless browser
route. Set `CRON_SECRET` to a random value of at least 16 characters to activate
the protected scheduled-monitor endpoint registered in `vercel.json`. Set
`ORBIT_VAULT_KEY` to a stable base64-url encoded 32-byte key to activate saved
workflow credentials and notification destinations. Slack delivery needs no
additional provider secret; email delivery additionally requires
`ORBIT_RESEND_API_KEY` and `ORBIT_NOTIFICATION_FROM_EMAIL`.

## License

Private project.
