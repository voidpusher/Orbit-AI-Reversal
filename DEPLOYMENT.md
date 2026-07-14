# Deploying Orbit on Vercel

Orbit ships as one Vercel project. Next.js serves the UI and the protected queue/browser routes; FastAPI is exposed through `api/index.py` and the `/api/v1/*` rewrite.

## Standard deployment

1. Link the repository with `vercel link`.
2. Set `ORBIT_CAPTURE_SECRET` to a long random value.
3. Set `ORBIT_BROWSER_CAPTURE_URL=https://<your-domain>/api/browser-capture`.
4. Deploy with `vercel --prod` or push `main` when Git deployment is enabled.

Without managed storage, Orbit uses `/tmp/orbit.db` and completes analyses inline. That mode is suitable only for demos: data and reports are not durable across function instances.

## Durable analysis jobs

Vercel Queues is wired through the `orbit-analysis` trigger in `vercel.json`. Do not enable it until the project has shared Postgres storage.

1. Attach a managed Postgres database from the Vercel Marketplace. Marketplace-provided `DATABASE_URL` and `POSTGRES_URL` are detected automatically.
2. Set `ORBIT_QUEUE_DRIVER=vercel`.
3. Set `ORBIT_QUEUE_ENQUEUE_URL=https://<your-domain>/api/analysis-jobs/enqueue`.
4. Redeploy.

The API persists the analysis before publishing its UUID. Queue messages use that UUID as an idempotency key. The private consumer calls the protected FastAPI worker, which retries failed processing and safely returns completed reports on redelivery.

## Authenticated product analysis

Use **New analysis → Browser HAR** for products behind sign-in or bot protection. HAR sanitization happens in the browser. Orbit never uploads cookies, authorization headers, query strings, form data, or request/response bodies.
