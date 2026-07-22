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

## Notes

Authentication is disabled by default for local development. Production and
staging builds are protected by default; set `ORBIT_AUTH_DISABLED=true` and
`NEXT_PUBLIC_AUTH_DISABLED=true` only when intentionally publishing a shared demo.

## License

Private project.
