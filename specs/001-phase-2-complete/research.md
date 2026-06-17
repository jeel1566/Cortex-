# Research & Decisions: Phase 2 — Make it Complete

This document details the architectural decisions and technology choices selected to meet the Phase 2 requirements of the Cortex Knowledge OS.

---

## 1. Multi-Tenant Data Partitioning

### Decision
Implement strict physical isolation per tenant on the file system and database level.

### Rationale
- **SQLite Isolation**: Each tenant has their own SQLite database file (`data/tenants/{tenant_id}/metadata.db`). This ensures that database queries can never touch or bleed another tenant's records.
- **Vector Index Isolation**: The HNSW index file (`data/tenants/{tenant_id}/vector_index.json`) is loaded separately into memory per request or cached per tenant ID.
- **Git Repository Isolation**: Each tenant has their own separate git directory (`data/tenants/{tenant_id}/repo/`) initialized.
- **Alternatives Considered**: Shared databases with a `tenant_id` column were rejected to prevent leakage via developer SQL error, matching corporate confidentiality needs.

---

## 2. Git-based Page Store (`gitpython`)

### Decision
Use `gitpython` to manage the lifecycle of knowledge page files.

### Rationale
- Programmatically initializing and committing changes is simple and robust in Python.
- Every ingestion run, page update, or feedback correction executes:
  ```python
  repo.git.add(A=True)
  repo.index.commit(commit_message)
  ```
- **Alternatives Considered**: Running subprocess shell git commands was rejected for cleaner error handling and compatibility across operating systems.

---

## 3. Clerk Authentication & JWT Scopes

### Decision
Implement custom authorization middleware in FastAPI that decodes and validates Clerk JWT claims.

### Rationale
- Clerk encodes authorization scopes or metadata (e.g., `authority_level` field) inside the user's JWT.
- The FastAPI backend uses the public signing key of Clerk to decode the JWT, extract the `tenant_id` and `authority_level` (0 to 5), and check if the user is authorized to execute the endpoint.
- **Authority Levels Mapping**:
  - `L0` (Public): Access to public-only pages.
  - `L1` (Team Member): Query and view team-level pages.
  - `L2` (Contributor): Able to submit ingestion jobs.
  - `L3` (Moderator): Able to approve/reject drafts in the inbox.
  - `L4` (Manager): Able to flag page sensitivity or change tenant configs.
  - `L5` (Admin): Full tenant administration.

---

## 4. Notion Polling Connector

### Decision
A polling loop running in the background every 5 minutes using the Notion API.

### Rationale
- Webhook-based Notion updates require public HTTPS endpoints and are notoriously unstable or rate-limited.
- Polling Notion via `/pages` or `/databases` query filtering by `last_edited_time` is extremely simple, offline-testable, and robust.
