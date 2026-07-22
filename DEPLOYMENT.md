# Deploying Orbit on Vercel

Orbit ships as one Vercel project. Next.js serves the UI and the protected queue/browser routes; FastAPI is exposed through `api/index.py` and the `/api/v1/*` rewrite.

## Production deployment

1. Link the repository with `vercel link`.
2. Attach managed Postgres and confirm `DATABASE_URL` is present.
3. Set `ORBIT_CAPTURE_SECRET` to a long random value.
4. Set `ORBIT_BROWSER_CAPTURE_URL=https://<your-domain>/api/browser-capture`.
5. Set `NEXT_PUBLIC_SITE_URL=https://<your-domain>` for canonical metadata.
6. Keep authentication enabled with `ORBIT_AUTH_DISABLED=false` and
   `NEXT_PUBLIC_AUTH_DISABLED=false`. Production defaults to protected mode when
   these variables are omitted; set both to `true` only for an intentional demo.
7. Set `ORBIT_RUN_MIGRATIONS_ON_STARTUP=true` for the first schema deployment,
   then manage later migrations as an explicit release step.
8. Deploy with `vercel --prod` or push `main` when Git deployment is enabled.

The application exposes `/api/v1/healthz` through the Vercel API rewrite for
deployment monitoring. Without managed storage, Orbit uses `/tmp/orbit.db`; that
mode is suitable only for demos because accounts, jobs, and reports are not durable.

## Durable analysis jobs

Vercel Queues is wired through the `orbit-analysis` trigger in `vercel.json`. Do not enable it until the project has shared Postgres storage.

1. Attach a managed Postgres database from the Vercel Marketplace. Marketplace-provided `DATABASE_URL` and `POSTGRES_URL` are detected automatically.
2. Set `ORBIT_QUEUE_DRIVER=vercel`.
3. Set `ORBIT_QUEUE_ENQUEUE_URL=https://<your-domain>/api/analysis-jobs/enqueue`.
4. Redeploy.

The API persists the analysis before publishing its UUID. Queue messages use that UUID as an idempotency key. The private consumer calls the protected FastAPI worker, which retries failed processing and safely returns completed reports on redelivery.

## Authenticated product analysis

Use **New analysis → Browser HAR** for products behind sign-in or bot protection. HAR sanitization happens in the browser. Orbit never uploads cookies, authorization headers, query strings, form data, or request/response bodies.
