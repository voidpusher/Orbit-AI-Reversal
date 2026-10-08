# API specification

All endpoints are versioned under `/api/v1`, require an authenticated organization context, return JSON, and use RFC 9457-style problem responses. `Idempotency-Key` is required on job-creating requests.

| Method | Route | Description |
| --- | --- | --- |
| `POST` | `/analyses` | Validate target, create an analysis, enqueue exploration |
| `POST` | `/analyses/workflow` | Import sanitized Recorder actions with optional matching HAR evidence |
| `GET` | `/analyses/{analysis_id}` | Fetch status, options, and progress summary |
| `GET` | `/analyses/{analysis_id}/events` | Server-sent event stream for live progress |
| `POST` | `/analyses/{analysis_id}/cancel` | Request safe cancellation |
| `GET` | `/reports` | Paginated report list with `q`, `favorite`, `cursor` |
| `GET` | `/reports/{report_id}` | Full report projection and evidence references |
| `PATCH` | `/reports/{report_id}` | Update saved label/favorite state |
| `DELETE` | `/reports/{report_id}` | Soft-delete a report within tenant policy |
| `POST` | `/reports/{report_id}/exports` | Create signed PDF/JSON/Markdown export |
| `GET` | `/reports/{report_id}/workflows` | List report journeys available for contract compilation |
| `POST` | `/reports/{report_id}/workflows/compile` | Compile a journey into an evidence-linked contract and Playwright artifact |
| `POST` | `/reports/{report_id}/workflows` | Save or version a compiled contract and monitoring cadence |
| `GET` | `/reports/{report_id}/workflows/saved` | List persisted workflow definitions |
| `POST` | `/reports/{report_id}/workflows/{workflow_id}/runs` | Run an isolated replay with ephemeral runtime inputs |
| `GET` | `/reports/{report_id}/workflows/{workflow_id}/runs` | List redacted replay results and repair proposals |
| `GET` | `/workflows/run-due` | Protected Vercel Cron entrypoint for due daily/weekly monitors |
| `GET` | `/me` | Current identity, organization, entitlement summary |

## Create analysis

```json
POST /api/v1/analyses
{
  "target_url": "https://linear.app",
  "options": {
    "deep_crawl": false,
    "max_pages": 20,
    "capture_network_requests": true
  }
}
```

The service responds `202 Accepted` with an analysis identifier, status `queued`, and event-stream URL. Progress states are `queued`, `running`, `generating_report`, `completed`, `failed`, and `cancelled`.

## Compile workflow

```json
POST /api/v1/reports/{report_id}/workflows/compile
{
  "flow_name": "Primary activation flow"
}
```

The response contains an `orbit.workflow.v1` contract, evidence references,
automation readiness, unresolved blockers, a JSON export, and a Playwright
test starter. Inferred report steps remain marked as inferred and require an
authorized browser recording before Orbit labels the automation ready.

Runtime inputs sent to the replay endpoint are held only for that invocation;
they are excluded from workflow definitions, run records, audit metadata, and
error messages. Selector repair candidates never modify the contract
automatically and always carry `requires_approval: true`.

## Contract rules

Claims have `summary`, `confidence` (0–1), `classification` (`observed` or `inferred`), and at least one evidence reference. Cursor pagination is stable. The OpenAPI document is the source for generated client types.
