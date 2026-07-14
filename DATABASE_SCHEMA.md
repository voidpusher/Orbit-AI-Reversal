# Database schema

PostgreSQL is the source of truth. UUIDv7 primary keys, UTC timestamps, `created_at`, `updated_at`, and `organization_id` are standard on tenant-owned tables.

| Table | Purpose | Key fields |
| --- | --- | --- |
| `users` | Human identities | `id`, `email`, `name`, `avatar_url`, `status` |
| `organizations` | Tenant boundary | `id`, `name`, `slug`, `plan` |
| `organization_members` | Roles | `organization_id`, `user_id`, `role` |
| `analyses` | Requested exploration | `id`, `target_url`, `status`, `options_json`, `requested_by_id`, `started_at`, `completed_at` |
| `analysis_events` | Append-only progress log | `analysis_id`, `sequence`, `kind`, `payload_json`, `occurred_at` |
| `evidence_items` | Sanitized observed artifacts | `analysis_id`, `kind`, `uri`, `content_hash`, `metadata_json`, `redaction_version` |
| `reports` | Versioned report projection | `id`, `analysis_id`, `version`, `summary_json`, `published_at` |
| `report_claims` | Individual observable/inferred statements | `report_id`, `section`, `claim`, `confidence`, `classification`, `model_version` |
| `claim_evidence` | Claim-to-evidence relation | `claim_id`, `evidence_item_id`, `relevance` |
| `saved_reports` | User organization bookmarks | `organization_id`, `report_id`, `is_favorite`, `label` |
| `api_keys` | Programmatic access | `organization_id`, `key_prefix`, `secret_hash`, `last_used_at`, `revoked_at` |
| `audit_logs` | Security-relevant actions | `organization_id`, `actor_id`, `action`, `target_type`, `target_id`, `metadata_json` |

## Important constraints and indexes

- Unique `(organization_id, slug)` for organizations and `(analysis_id, sequence)` for events.
- `reports.analysis_id` is unique for the first production report; later versions use unique `(analysis_id, version)`.
- Index `analyses(organization_id, created_at DESC)`, `reports(organization_id, published_at DESC)`, and a GIN index for report search projection.
- Foreign keys use restrictive deletes for evidence/reports; users are soft-deactivated to retain audit integrity.
- `analysis_events` and audit logs are partition candidates by month as volumes grow.
