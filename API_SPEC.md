# API specification

All endpoints are versioned under `/api/v1`, require an authenticated organization context, return JSON, and use RFC 9457-style problem responses. `Idempotency-Key` is required on job-creating requests.

| Method | Route | Description |
| --- | --- | --- |
| `POST` | `/analyses` | Validate target, create an analysis, enqueue exploration |
| `GET` | `/analyses/{analysis_id}` | Fetch status, options, and progress summary |
| `GET` | `/analyses/{analysis_id}/events` | Server-sent event stream for live progress |
| `POST` | `/analyses/{analysis_id}/cancel` | Request safe cancellation |
| `GET` | `/reports` | Paginated report list with `q`, `favorite`, `cursor` |
| `GET` | `/reports/{report_id}` | Full report projection and evidence references |
| `PATCH` | `/reports/{report_id}` | Update saved label/favorite state |
| `DELETE` | `/reports/{report_id}` | Soft-delete a report within tenant policy |
| `POST` | `/reports/{report_id}/exports` | Create signed PDF/JSON/Markdown export |
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

## Contract rules

Claims have `summary`, `confidence` (0–1), `classification` (`observed` or `inferred`), and at least one evidence reference. Cursor pagination is stable. The OpenAPI document is the source for generated client types.
