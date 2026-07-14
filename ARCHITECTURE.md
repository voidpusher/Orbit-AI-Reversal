# Architecture

## System overview

Orbit accepts an authorized public SaaS URL, creates an immutable analysis job, and runs a controlled browser exploration in an isolated worker. The worker records observable evidence only: navigated pages, screenshots, public network metadata, DOM-derived signals, and timing. An inference pipeline converts evidence into structured report claims; every claim carries evidence references, a confidence score, model/prompt version, and timestamps.

```text
Next.js web → FastAPI → Postgres (accounts, jobs, reports)
                    ↘ Redis (queue, stream, cache) → Playwright workers
                                                   → object storage (screens/evidence)
                                                     ↘ GPT-5 inference pipeline
```

## Principles

- **Evidence before inference.** Never present inferred implementation details as facts.
- **Least-privilege exploration.** Public pages only by default; authentication requires an explicit future consent flow.
- **Async by design.** A job state machine and streamed events make crawling resilient and observable.
- **Versioned outputs.** Reports are reproducible against their evidence and inference versions.
- **Tenant isolation.** Every persisted resource has an organization boundary and authorization policy.

## Core flow

1. The web client validates a URL and creates an `analysis`.
2. FastAPI emits a queued job to Redis after storing it transactionally in Postgres.
3. A Playwright worker applies scope, rate, and page-budget controls; it streams progress events.
4. Extractors normalize evidence, detect technologies, and build a graph of observed pages, interfaces, and requests.
5. GPT-5 produces schema-constrained claims. Validation rejects claims without supporting evidence.
6. A report projection is saved and the client receives real-time progress via SSE.

## Security and reliability

- SSRF defenses: DNS/IP allow/deny checks, redirect revalidation, egress policy, URL allowlist controls.
- Browser isolation: ephemeral contexts, no persisted user credentials, download blocking, request budgets.
- Encrypt secrets and provider tokens at rest; redact sensitive headers, query parameters, and DOM values.
- Structured JSON logs, trace IDs, audit logs, idempotency keys, retries with dead-letter queues.
- Row-level tenancy enforcement, rate limits, CSP, CSRF protections where sessions are used.

## Boundaries

The frontend owns presentation and local interaction state. The API owns authorization, durable job state, and report access. Workers own browser execution; they never directly serve user traffic. Model adapters own prompting and structured-output validation, allowing provider changes without rewriting product domains.
