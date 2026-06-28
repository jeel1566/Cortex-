# Feature Specification: Notion Ingestion & Page Validation Fixes

**Feature Branch**: `002-notion-ingestion-fixes`

**Created**: 2026-06-28

**Status**: Draft

**Input**: User description: "Fix Notion ingestion fallback, bad synthesis output, and missing schema validation"

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Accurate Notion Ingestion Crawler (Priority: P1)
As a knowledge owner, I want the system to index all accessible documents and databases from my Notion workspace without silent fallbacks or sample data generation, so that the knowledge base accurately reflects our internal information.
* **Why this priority**: Correct ingestion is foundational. Users expect their actual company data, not placeholder demo text.
* **Independent Test**: Run a Notion sync job with empty/unshared Notion credentials or zero shared pages. Verify the job fails loudly with an error reporting 0 documents found, instead of creating fallback demo pages.
* **Acceptance Scenarios**:
  1. **Given** a Notion integration with 0 accessible pages, **When** `/v1/sync/all` is called, **Then** the API returns a clear error or status showing 0 documents found and logs the check.
  2. **Given** a shared Notion document with sections, paragraphs, tables, and code blocks, **When** sync runs, **Then** it fetches the blocks recursively, compiles them into a single `SourceDocument`, and chunks them by headers/sections.

### User Story 2 - Notion Access Check UI (Priority: P2)
As a knowledge admin, I want to see an overview of what pages and databases are discovered in Notion before proceeding with ingestion.
* **Why this priority**: Helps admins verify that the Notion connection is working and has permissions to see the correct pages.
* **Independent Test**: Open settings or dashboard in the UI, check the Notion Connection status, and see a list of discovered pages, databases, skipped empty pages, and inaccessible objects.
* **Acceptance Scenarios**:
  1. **Given** a connected Notion integration, **When** loading the sync/overview UI, **Then** the system displays the total pages found, databases found, and skips empty pages.

### User Story 3 - Strict Output Gate and YAML Validation (Priority: P1)
As a system administrator, I want every generated page to be strictly validated for format and prompt leakage before committing it to git, ensuring malformed drafts never contaminate the knowledge base.
* **Why this priority**: Prevents bad or prompt-leaked LLM outputs (e.g. including "Expected Output" or "</output_format>") from being saved or approved.
* **Independent Test**: Feed the synthesizer a prompt designed to leak meta-commentary or lack YAML header. Verify the validator catches it, rejects the page, marks the job as `failed` (or `draft` in the db), and prevents any commit to git.
* **Acceptance Scenarios**:
  1. **Given** synthesized output containing prompt leakage (e.g. `</output_format>`), **When** validating the page, **Then** validation fails and git commit is aborted.
  2. **Given** synthesized output that doesn't start with `---` or fails YAML parsing, **When** validating, **Then** it is rejected and marked failed.

---

## Edge Cases

- **Rate Limits & API Quotas**: Notion APIs have rate limits. If block retrieval is recursive and heavy, we must throttle requests and queue retries.
- **Empty Databases / Empty Pages**: Discovered pages might have no content. These should be logged and skipped rather than generating empty stub pages or failing the entire job.
- **Git Commit Clashes**: Multiple ingestion jobs running concurrently might try to commit to the same tenant repository. A write lock on the repository is needed.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST NOT write fallback demo text ("Cortex supports Slack...") during ingestion if Notion fetches 0 documents or errors. It must fail the ingestion job.
- **FR-002**: System MUST recursively fetch all block children of a Notion page (headings, paragraphs, lists, code, tables, child pages) to compile a complete representation.
- **FR-003**: System MUST store raw text from Notion as a structured `SourceDocument` (or raw source block metadata) before chunking, preserving context.
- **FR-004**: System MUST chunk source documents by headings/sections (using heading blocks or Markdown headings) rather than arbitrary sentence clusters.
- **FR-005**: System MUST maintain a `notion_objects` registry table mapping: `notion_id`, `tenant_id`, `title`, `url`, `parent_id`, `last_edited_time`, `type`, and `sync_status`.
- **FR-006**: System MUST enforce a strict pre-save validator:
  - Must start with `---` and end the frontmatter block.
  - Must parse as valid YAML frontmatter containing required keys: `id`, `title`, `sources`, `propositions`, `synthesis_validation`.
  - Must not contain substrings like `"Expected Output"`, `"Input JSON"`, `"</output_format>"`, or assistant prompt-leak boilerplate.
- **FR-007**: System MUST reject any generated page failing the validator and MUST NOT commit the rejected page to the tenant's Git repository.
- **FR-008**: System MUST provide an endpoint or database query to retrieve connection metrics (discovered pages, databases, skipped pages) to present on the Notion Access Check screen.

### Key Entities

- **SourceDocument**: Raw content extracted from Notion/other connectors before synthesis. Retains the original structural hierarchy.
- **NotionObject**: Entry in SQLite representing a discovered Notion page or database, containing metadata, sync timestamps, parent references, and access permissions.
- **IngestionJob**: Updated status values: `queued`, `processing`, `complete`, `failed` (for validation errors or fetch errors).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of pages written to Git must parse as valid Markdown with valid YAML headers, containing 0 instances of prompt leakage.
- **SC-002**: An empty sync attempt must complete and return a `400 Bad Request` or specific failure code/message in under 200ms, with 0 commits added.
- **SC-003**: Notion block parsing must support at least 6 common block types (paragraph, heading_1/2/3, bulleted_list_item, numbered_list_item, code, table).
- **SC-004**: Ingestion job state must reflect `failed` on schema/validation errors or fetch errors within 1 second of failure.

---

## Assumptions

- We are using the standard Notion API with an integration token provided by the user.
- The Notion Integration is granted read access to the target workspace or specific pages.
- FastEmbed and SQLite are used locally for document chunking and metadata storage.
