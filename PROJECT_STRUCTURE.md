# Orbit project structure

Orbit is a monorepo organised by deployable service and product domain.

```text
orbit/
├─ apps/
│  ├─ web/                         # Next.js App Router product surface
│  │  ├─ app/                      # Route groups, layouts, loading/error states
│  │  ├─ components/               # Shared, accessible presentation primitives
│  │  ├─ features/                 # Domain modules: analyses, reports, billing
│  │  ├─ lib/                      # API client, validation, utilities
│  │  └─ types/                    # UI-facing contracts
│  └─ api/                         # FastAPI service
│     └─ app/
│        ├─ api/                   # Versioned route handlers
│        ├─ domains/                # Application services by bounded context
│        ├─ workers/                # Crawl/inference job orchestration
│        ├─ models/                 # SQLAlchemy persistence models
│        └─ core/                   # Config, logging, auth, database
├─ packages/
│  ├─ contracts/                   # Shared OpenAPI-generated types (future)
│  └─ prompts/                     # Versioned model prompts and schemas
├─ infrastructure/                 # Docker, migrations, deployment manifests
├─ docs/                           # Operational runbooks and ADRs
└─ *.md                            # Product architecture and delivery plan
```

The first implementation keeps the web app self-contained while preserving the feature boundaries above. API contracts are intentionally explicit so the browser and worker infrastructure can evolve independently.
