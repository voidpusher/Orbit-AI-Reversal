# UI flow

## Primary journey

1. Visitor learns the product on the landing page and selects **Analyze software**.
2. Authenticated users land in **New analysis**, paste a URL, and select bounded crawl options.
3. Submission opens **Live analysis**, where streamed browser and inference steps are visible with an estimated state and live log.
4. Completion routes to the **Report viewer**, opening with an evidence-backed overview.
5. Users navigate report domains, favorite/export it, return to **Reports**, or start a new analysis.

## Page responsibilities

| Page | Primary action | Key states |
| --- | --- | --- |
| Landing | Start analysis / view example | public, responsive navigation |
| Authentication | sign in via email/provider | validation, provider failure |
| Dashboard | resume or start work | empty, loading, report list |
| New analysis | configure and submit job | validation, limits, submitting |
| Live analysis | observe / cancel job | queued, running, failed, complete |
| Report viewer | navigate evidence-backed findings | loading, section empty, export-ready |
| Saved reports | search, favorite, delete | empty, search no-result |
| Settings | manage account and API settings | saved, permission-limited |

## Interaction standards

All primary actions remain keyboard reachable with visible focus. Form errors are announced, analysis progress uses semantic progress updates, and diagrams have a textual equivalent. Desktop report navigation collapses to a menu on narrow screens.
