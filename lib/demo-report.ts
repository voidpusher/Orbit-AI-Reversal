"use client";

import type { CompiledWorkflow, ReportDocument, WorkflowContract } from "./types";

export const DEMO_WORKFLOW_CONTRACT: WorkflowContract = {
  version: "orbit.workflow.v1",
  id: "linear-app.create-and-assign-an-issue",
  name: "Create and assign an issue",
  product_name: "Linear",
  target_url: "https://linear.app/acme/team/active",
  classification: "observed",
  confidence: 92,
  automation_readiness: 86,
  status: "ready",
  steps: [
    { id: "step-1", order: 1, action: "Open workspace", kind: "navigate", classification: "observed", confidence: 98, evidence_ids: ["E1"], requires_review: false },
    { id: "step-2", order: 2, action: "Create issue", kind: "interaction", classification: "observed", confidence: 94, evidence_ids: ["E1", "E2"], requires_review: false },
    { id: "step-3", order: 3, action: "Set assignee", kind: "interaction", classification: "observed", confidence: 91, evidence_ids: ["E2"], requires_review: false },
    { id: "step-4", order: 4, action: "Submit issue", kind: "interaction", classification: "observed", confidence: 96, evidence_ids: ["E2", "E3"], requires_review: false },
    { id: "step-5", order: 5, action: "Confirm realtime update", kind: "assertion", classification: "observed", confidence: 89, evidence_ids: ["E3"], requires_review: false },
  ],
  endpoints: [
    { method: "POST", path: "/api/graphql", confidence: 96, classification: "observed", evidence_ids: ["E2"] },
    { method: "WS", path: "/realtime", confidence: 91, classification: "observed", evidence_ids: ["E3"] },
  ],
  evidence: [
    { id: "E1", source: "Browser recording", detail: "Issue composer opened from the workspace action menu.", classification: "observed", confidence: 98 },
    { id: "E2", source: "GraphQL operation", detail: "IssueCreate mutation carried title, team, and assignee identifiers.", classification: "observed", confidence: 96 },
    { id: "E3", source: "Realtime event", detail: "Websocket issue.created event confirmed the committed record.", classification: "observed", confidence: 91 },
  ],
  unknowns: [
    "The server-side authorization policy is not visible in the client capture.",
    "The generated selectors should be checked after major interface releases.",
  ],
};

export const DEMO_PLAYWRIGHT = `import { test, expect } from '@playwright/test';

test('Create and assign an issue', async ({ page }) => {
  await page.goto('https://linear.app/acme/team/active');

  await test.step('Create issue', async () => {
    await page.getByRole('button', { name: /create issue/i }).click();
    await page.getByPlaceholder(/issue title/i).fill('Investigate checkout latency');
  });

  await test.step('Assign and submit', async () => {
    const mutation = page.waitForResponse((response) =>
      response.url().includes('/api/graphql') && response.request().method() === 'POST'
    );
    await page.getByRole('button', { name: /assignee/i }).click();
    await page.getByRole('option', { name: /sanchit/i }).click();
    await page.getByRole('button', { name: /create issue/i }).click();
    await mutation;
  });

  await expect(page.getByText('Investigate checkout latency')).toBeVisible();
});
`;

export const DEMO_COMPILED_WORKFLOW: CompiledWorkflow = {
  contract: DEMO_WORKFLOW_CONTRACT,
  playwright: DEMO_PLAYWRIGHT,
  contract_json: JSON.stringify(DEMO_WORKFLOW_CONTRACT, null, 2),
};

export const DEMO_ARCHITECTURE: ReportDocument["architecture"] = {
  summary:
    "A browser-delivered React application behind an edge network, with a GraphQL API, realtime updates, asynchronous workers, and managed data services.",
  confidence: 86,
  reasoning:
    "The model combines public network requests, loaded bundles, route behavior, response headers, and third-party SDK signatures. Server-side components are inferred only when the client contract or request flow requires them.",
  evidence: [
    "React and Next.js chunks are loaded from the application origin.",
    "GraphQL requests target /api/graphql and carry bearer authorization.",
    "A websocket upgrade is observed at /realtime.",
    "Stripe and analytics SDKs are present in production bundles.",
  ],
  edges: [],
  nodes: [
    {
      id: "browser",
      label: "Browser client",
      kind: "client",
      role: "User-facing runtime",
      confidence: 100,
      classification: "observed",
      responsibilities: ["Render the interface", "Manage navigation", "Send authenticated requests"],
      evidence: ["https://linear.app", "HTML document and JavaScript execution observed"],
    },
    {
      id: "edge",
      label: "Cloudflare edge",
      kind: "edge",
      role: "Delivery and traffic boundary",
      confidence: 96,
      classification: "observed",
      responsibilities: ["TLS termination", "Static asset caching", "Request routing"],
      evidence: ["Response header: server=cloudflare", "CF-Ray header present"],
    },
    {
      id: "frontend",
      label: "React frontend",
      kind: "frontend",
      role: "Application shell",
      confidence: 98,
      classification: "observed",
      responsibilities: ["Client routing", "Feature composition", "Optimistic UI state"],
      evidence: ["/_next/static/chunks/app.js", "React runtime markers found"],
    },
    {
      id: "api",
      label: "GraphQL API",
      kind: "api",
      role: "Product service boundary",
      confidence: 93,
      classification: "observed",
      responsibilities: ["Resolve product queries", "Authorize mutations", "Shape client contracts"],
      evidence: ["POST https://linear.app/api/graphql", "application/json GraphQL response"],
    },
    {
      id: "realtime",
      label: "Realtime gateway",
      kind: "realtime",
      role: "Live synchronization",
      confidence: 91,
      classification: "observed",
      responsibilities: ["Fan out workspace changes", "Maintain presence", "Reconnect clients"],
      evidence: ["wss://linear.app/realtime", "HTTP 101 protocol upgrade"],
    },
    {
      id: "worker",
      label: "Background workers",
      kind: "worker",
      role: "Asynchronous execution",
      confidence: 69,
      classification: "inferred",
      responsibilities: ["Process imports", "Generate exports", "Dispatch notifications"],
      evidence: ["Import operation returns a job identifier", "Export status is polled asynchronously"],
    },
    {
      id: "database",
      label: "PostgreSQL",
      kind: "database",
      role: "System of record",
      confidence: 68,
      classification: "inferred",
      responsibilities: ["Persist workspace state", "Maintain relational integrity", "Support transactional writes"],
      evidence: ["Relational identifiers and cursor pagination observed in API responses"],
    },
    {
      id: "storage",
      label: "Object storage",
      kind: "storage",
      role: "Binary asset storage",
      confidence: 88,
      classification: "observed",
      responsibilities: ["Store attachments", "Serve signed downloads", "Retain exports"],
      evidence: ["Signed object URLs observed on attachment downloads"],
    },
    {
      id: "auth",
      label: "Identity provider",
      kind: "auth",
      role: "Authentication service",
      confidence: 84,
      classification: "observed",
      responsibilities: ["Authenticate users", "Issue sessions", "Handle OAuth callbacks"],
      evidence: ["/oauth/callback route", "Session cookie and bearer token observed"],
    },
    {
      id: "stripe",
      label: "Stripe",
      kind: "payment",
      role: "Billing provider",
      confidence: 95,
      classification: "observed",
      responsibilities: ["Collect payment details", "Manage subscriptions"],
      evidence: ["https://js.stripe.com/v3", "Stripe publishable key pattern"],
    },
    {
      id: "analytics",
      label: "Product analytics",
      kind: "analytics",
      role: "Behavior telemetry",
      confidence: 89,
      classification: "observed",
      responsibilities: ["Capture product events", "Measure journeys"],
      evidence: ["Analytics event batch observed after navigation"],
    },
  ],
  connections: [
    { from: "browser", to: "edge", label: "Page and asset requests", protocol: "HTTPS", confidence: 100, classification: "observed", evidence: ["GET https://linear.app"] },
    { from: "edge", to: "frontend", label: "Application delivery", protocol: "HTTPS", confidence: 97, classification: "observed", evidence: ["Cached Next.js assets returned through edge"] },
    { from: "frontend", to: "api", label: "Queries and mutations", protocol: "GraphQL/HTTPS", confidence: 94, classification: "observed", evidence: ["POST /api/graphql"] },
    { from: "frontend", to: "realtime", label: "Workspace events", protocol: "WebSocket", confidence: 91, classification: "observed", evidence: ["wss://linear.app/realtime"] },
    { from: "frontend", to: "auth", label: "Sign-in and session", protocol: "OAuth 2.0", confidence: 84, classification: "observed", evidence: ["/oauth/callback"] },
    { from: "api", to: "worker", label: "Enqueue long-running work", protocol: "Job queue", confidence: 69, classification: "inferred", evidence: ["202 response includes jobId"] },
    { from: "api", to: "database", label: "Transactional reads and writes", protocol: "SQL", confidence: 68, classification: "inferred", evidence: ["Relational response shapes and transactional mutation behavior"] },
    { from: "api", to: "storage", label: "Attachment metadata", protocol: "HTTPS", confidence: 86, classification: "observed", evidence: ["Signed attachment URL returned by API"] },
    { from: "worker", to: "storage", label: "Export artifacts", protocol: "Object API", confidence: 67, classification: "inferred", evidence: ["Completed exports resolve to signed object URLs"] },
    { from: "frontend", to: "stripe", label: "Checkout session", protocol: "Stripe.js", confidence: 95, classification: "observed", evidence: ["Stripe.js loaded on billing route"] },
    { from: "frontend", to: "analytics", label: "Product events", protocol: "HTTPS", confidence: 89, classification: "observed", evidence: ["Analytics batch request"] },
  ],
  layers: [
    { name: "Client", node_ids: ["browser", "frontend"] },
    { name: "Delivery", node_ids: ["edge"] },
    { name: "Application", node_ids: ["api", "realtime", "worker"] },
    { name: "Data", node_ids: ["database", "storage"] },
    { name: "External services", node_ids: ["auth", "stripe", "analytics"] },
  ],
  request_flows: [
    { name: "Page delivery", steps: ["browser", "edge", "frontend"], transport: "HTTPS", confidence: 98, classification: "observed", evidence: ["Initial document and chunk waterfall"] },
    { name: "Issue query", steps: ["browser", "frontend", "api", "database"], transport: "GraphQL + SQL", confidence: 82, classification: "inferred", evidence: ["GraphQL request and relational response shape"] },
    { name: "Realtime update", steps: ["browser", "frontend", "realtime"], transport: "WebSocket", confidence: 91, classification: "observed", evidence: ["Live websocket messages"] },
    { name: "Export job", steps: ["frontend", "api", "worker", "storage"], transport: "HTTPS + queue", confidence: 68, classification: "inferred", evidence: ["Asynchronous export lifecycle"] },
    { name: "Checkout", steps: ["frontend", "stripe", "api"], transport: "Stripe.js + HTTPS", confidence: 90, classification: "observed", evidence: ["Billing journey network trace"] },
  ],
  trust_boundaries: [
    { name: "Public to authenticated application", between: ["edge", "api"], implication: "Session validation and authorization are required before product data is returned.", confidence: 91, evidence: ["Bearer authorization and session cookie observed"] },
    { name: "Application to managed providers", between: ["api", "stripe"], implication: "Provider credentials, webhooks, and signed payloads cross an external trust boundary.", confidence: 84, evidence: ["Stripe integration surface detected"] },
  ],
  patterns: [
    { title: "Edge-delivered SPA", detail: "A cached application shell calls a separate product API after hydration.", confidence: 94, classification: "observed", evidence: ["Next.js assets and post-load API requests"] },
    { title: "Event-driven background work", detail: "Long-running imports and exports appear to be handed off to asynchronous workers.", confidence: 69, classification: "inferred", evidence: ["Job identifiers and status polling"] },
  ],
  unknowns: [
    "The exact queue technology is not exposed by public evidence.",
    "PostgreSQL is inferred from relational behavior; the database vendor is not directly observable.",
  ],
};


const SAMPLE_ENTITIES: ReportDocument["entities"]["items"] = [
  { name: "Workspace", fields: ["id", "name", "url_key"], confidence: 94 },
  { name: "Team", fields: ["id", "workspace_id", "name", "key"], confidence: 92 },
  { name: "User", fields: ["id", "name", "email"], confidence: 93 },
  { name: "Issue", fields: ["id", "team_id", "assignee_id", "title", "status", "priority"], confidence: 96 },
  { name: "Comment", fields: ["id", "issue_id", "author_id", "body"], confidence: 87 },
];
const SAMPLE_RELATIONSHIPS = [
  { from: "Workspace", to: "Team", kind: "one-to-many" },
  { from: "Team", to: "Issue", kind: "one-to-many" },
  { from: "User", to: "Issue", kind: "assigned-to" },
  { from: "Issue", to: "Comment", kind: "one-to-many" },
];

export const DEMO_REPORT: ReportDocument = {
  meta: {
    product_name: "Linear", host: "linear.app", url: "https://linear.app",
    pages_explored: 12, evidence_count: 94, features_count: 4, technologies_count: 4,
    insights_count: 3, overall_confidence: 86, confidence_band: "Strong evidence",
    generated_at: "2026-10-09T00:00:00.000Z", model_name: "Illustrative demo",
  },
  overview: {
    headline: "An issue-tracking workspace with keyboard-driven workflows and realtime collaboration.",
    summary: "Illustrative reconstruction for exploring Orbit. These sample observations are not a verified audit of Linear.",
    metrics: [
      { value: "4", label: "Features", sub: "Illustrative workflows" },
      { value: String(DEMO_ARCHITECTURE.nodes.length), label: "Components", sub: "Observed and inferred" },
      { value: String(SAMPLE_ENTITIES.length), label: "Core entities", sub: "With relationships" },
      { value: "94", label: "Evidence records", sub: "Sample dataset" },
    ],
  },
  architecture: DEMO_ARCHITECTURE,
  user_flows: {
    summary: "An issue-creation journey from composer to realtime confirmation.",
    confidence: 92,
    reasoning: "Sample capture correlates the issue composer, mutation, and realtime event.",
    flows: [
      { name: "Create and assign an issue", steps: ["Open workspace", "Create issue", "Set assignee", "Submit issue", "Confirm realtime update"], confidence: 92, classification: "observed" },
      { name: "Export team issues", steps: ["Open team", "Choose export", "Start job", "Download artifact"], confidence: 68, classification: "inferred" },
    ],
  },
  features: {
    summary: "Capabilities represented in the sample product journeys.", confidence: 91,
    items: [
      { name: "Issue creation", description: "Create an issue with title, priority, and assignee.", confidence: 96, classification: "observed", evidence: ["Sample composer and IssueCreate operation"] },
      { name: "Team workspaces", description: "Group issues and members within a team.", confidence: 94, classification: "observed", evidence: ["Sample team routes and workspace identifiers"] },
      { name: "Realtime updates", description: "Synchronize changes across active clients.", confidence: 91, classification: "observed", evidence: ["Sample issue.created websocket event"] },
      { name: "Background export", description: "Compile an export asynchronously and download the result.", confidence: 68, classification: "inferred", evidence: ["Sample export job identifier and status polling"] },
    ],
  },
  entities: {
    summary: "Product objects represented in the sample API contracts.", confidence: 92,
    items: SAMPLE_ENTITIES, relationships: SAMPLE_RELATIONSHIPS,
    reasoning: "Entity fields describe the example client contract, not a verified internal schema.",
  },
  database: {
    summary: "An inferred relational model; the internal database and vendor are not directly observable.", confidence: 68,
    items: SAMPLE_ENTITIES.map((entity) => ({ ...entity, confidence: 68 })),
    relationships: SAMPLE_RELATIONSHIPS,
    reasoning: "Relationships suggest foreign-key-style references. Table names, indexes, storage, and replication remain unknown.",
  },
  permissions: {
    summary: "Illustrative role boundaries for a team workspace.", confidence: 65,
    roles: [
      { name: "Workspace administrator", capabilities: ["Manage workspace settings", "Invite and remove members", "Manage billing"] },
      { name: "Team member", capabilities: ["Create and edit issues", "Assign issues", "Add comments"] },
      { name: "Guest", capabilities: ["Read shared content", "Limited participation"] },
    ],
    reasoning: "These roles are inferred examples. Server-side authorization policies are not visible in the client capture.",
  },
  api: {
    summary: "Sample GraphQL operations and a websocket transport.", confidence: 93,
    style: "GraphQL + WebSocket",
    endpoints: [
      { method: "POST", path: "/api/graphql", confidence: 96, note: "Queries and IssueCreate mutation" },
      { method: "WS", path: "/realtime", confidence: 91, note: "Workspace events and presence" },
    ],
    evidence: ["Sample POST request with operationName=IssueCreate", "Sample websocket issue.created event"],
    spec: null,
  },
  tech_stack: {
    summary: "Example client and provider signals.", confidence: 93, categories: ["Frontend", "API", "Realtime", "Billing"],
    items: [
      { name: "React / Next.js", category: "Frontend", confidence: 98, evidence: ["Sample /_next/static application chunks"] },
      { name: "GraphQL", category: "API", confidence: 93, evidence: ["Sample GraphQL operation envelope"] },
      { name: "WebSocket", category: "Realtime", confidence: 91, evidence: ["Sample HTTP 101 upgrade"] },
      { name: "Stripe", category: "Billing", confidence: 95, evidence: ["Sample billing-provider SDK signature"] },
    ],
  },
  integrations: {
    summary: "Managed services represented in the demo model.", confidence: 89,
    items: [
      { name: "Stripe", category: "Billing", confidence: 95, evidence: ["Sample billing journey"] },
      { name: "Identity provider", category: "Authentication", confidence: 86, evidence: ["Sample session exchange"] },
    ],
  },
  insights: {
    summary: "What the sample evidence supports, with inference kept explicit.", confidence: 81,
    items: [
      { title: "Realtime collaboration", detail: "A websocket path synchronizes workspace changes alongside API traffic.", confidence: 91, classification: "observed" },
      { title: "Asynchronous exports", detail: "Job identifiers and polling suggest a worker boundary.", confidence: 69, classification: "inferred" },
      { title: "Provider boundaries", detail: "Authentication and billing cross managed-service boundaries.", confidence: 84, classification: "inferred" },
    ],
  },
  infrastructure: { summary: "Example edge and managed-data boundaries.", confidence: 78, items: [
    { title: "Edge delivery", detail: "Application assets pass through an edge cache.", confidence: 96 },
    { title: "Managed data services", detail: "A relational system of record is inferred; its vendor is unverified.", confidence: 68 },
  ] },
  security: { summary: "Sample security observations, not a security assessment.", confidence: 74, findings: [
    { title: "Authenticated requests", detail: "The sample API request carries authorization.", status: "info", evidence: "Sample bearer authorization header; credentials omitted" },
    { title: "Server authorization unknown", detail: "Client evidence cannot confirm record-level permissions.", status: "warn" },
  ] },
};

