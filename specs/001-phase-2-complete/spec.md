# Feature Specification: Phase 2 — Make it Complete

**Feature Branch**: `001-phase-2-complete`

**Created**: 2026-06-17

**Status**: Draft

**Input**: User description: "let's start making phase 2 use skills to"

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Git-backed Version Control & Sensitivity Tagging (Priority: P1)
As a compliance officer, I want every change to the company knowledge base to be tracked in Git and every proposition tagged with sensitivity levels so that we have an audit trail and data access control.
* **Why this priority**: Crucial for corporate auditability and solving the "permission poison" problem before scaling.
* **Independent Test**: Run a local ingestion job; verify a new commit is created in the tenant's git repository and the synthesized markdown frontmatter contains sensitivity levels.
* **Acceptance Scenarios**:
  1. **Given** a tenant git repo, **When** new logs are ingested, **Then** a commit is created with a message describing the update.
  2. **Given** a synthesized page, **When** inspecting YAML frontmatter, **Then** all claims/propositions are tagged with `public`, `team`, or `confidential`.

### User Story 2 - Multi-Tenant Isolation & Clerk Authorization (Priority: P1)
As an enterprise customer, I want my data (vector index, SQLite, git repo) completely isolated from other companies, and access restricted by user clearance level.
* **Why this priority**: Required for customer security and privacy.
* **Independent Test**: Query tenant A and tenant B concurrently; verify zero data leakage and check that a low-clearance user cannot retrieve confidential pages.
* **Acceptance Scenarios**:
  1. **Given** two tenants, **When** querying tenant A, **Then** no records from tenant B are returned.
  2. **Given** an authority level L1 user, **When** querying a page marked with L3 clearance, **Then** the request is blocked with an HTTP 403.

### User Story 3 - Notion Connector & Feedback Loops (Priority: P2)
As a team leader, I want to sync documents from Notion on a 5-minute poll schedule and submit feedback on incorrect answers to trigger automatic re-synthesis.
* **Why this priority**: Closed-loop feedback allows the system to auto-correct errors.
* **Independent Test**: Poll Notion for new edits, and submit a feedback request to verify re-synthesis starts.
* **Acceptance Scenarios**:
  1. **Given** a Notion connector configured, **When** a page changes on Notion, **Then** it is ingested within 5 minutes.
  2. **Given** a user feedback event, **When** `POST /v1/feedback` is called, **Then** the flagged page runs through the synthesizer and validator loop.

### User Story 4 - Admin Approval Inbox UI (Priority: P2)
As a knowledge administrator, I want an admin panel UI where I can review, edit, approve, or reject proposed changes.
* **Why this priority**: Crucial for human-in-the-loop validation of AI-generated pages.
* **Independent Test**: Open Next.js dashboard, review a pending page, click approve, and check that status switches from `DRAFT` to `APPROVED`.
* **Acceptance Scenarios**:
  1. **Given** a pending synthesis result, **When** opening the approval inbox, **Then** the draft content and sources are displayed.
  2. **Given** a draft in the inbox, **When** the admin clicks Approve, **Then** the page is saved and indexed.

---

## Edge Cases

- **Auth Token Expiration**: If a Clerk JWT expires mid-query, request is rejected with HTTP 401.
- **Git Merge Conflicts**: If multiple ingestion pipelines edit a page simultaneously, resolve using lock mechanisms or linear history.
- **Notion Rate Limiting**: If Notion API throws 429, implement back-off and retry queuing.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST initiate a Git repository per tenant and commit every page update.
- **FR-002**: Page YAML headers MUST include sensitivity tags for claim-level clearance checks.
- **FR-003**: System MUST provide strict physical isolation (separate SQLite, Git repo, and HNSW indexes) per tenant.
- **FR-004**: System MUST check user authority levels (L0-L5) via Clerk JWT claims before serving or editing content.
- **FR-005**: Notion connector MUST run on a 5-minute poll-based interval.
- **FR-006**: System MUST expose `/v1/feedback` endpoint which triggers re-synthesis when pages are flagged.
- **FR-007**: System MUST maintain three ingestion queues: immediate, standard (15-min), and background weekly.
- **FR-008**: System MUST export Prometheus metrics and output logs in JSON format via `structlog`.
- **FR-009**: System MUST provide a Next.js admin interface showing an Approval Inbox and a list-based Knowledge Explorer.

### Key Entities

- **Tenant**: Represents a company/organization. Has fields: `id`, `name`, `git_repo_path`, `hnsw_index_path`.
- **Page**: Markdown file version-controlled in Git. YAML has sensitivity, authors, sources, validation scores.
- **IngestionJob**: Tracked in SQLite with status (`queued`, `processing`, `complete`, `failed`, `awaiting_approval`).
- **Feedback**: Links feedback types to query IDs and page revisions.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Multi-tenant queries executed concurrently must show 0% data leakage across tenant indices.
- **SC-002**: Unauthorized query requests must return 403 Forbidden in less than 20ms.
- **SC-003**: Feedback submissions via `/v1/feedback` must start re-synthesis within 1 second.
- **SC-004**: Page retrieval on the Next.js Knowledge Explorer must load in under 150ms.

---

## Assumptions

- Clerk authentication endpoint configuration will be provided in `.env`.
- An active Git command-line tool is installed on the hosting server.
- SQLite is sufficient for MVP multi-tenant metadata storage (migration to PostgreSQL deferred).
