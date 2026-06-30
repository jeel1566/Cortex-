# Cortex New Engine Implementation Plan

## Goal

Build Cortex as a trusted, eventually executable Knowledge OS by replacing the current sentence-cluster page pipeline with a thin new engine that orchestrates source ingestion, raw evidence storage, draft compilation, validation, approval, Git truth, and permission-aware retrieval.

The engine must be a traffic controller, not a god-object.

```text
Connectors / uploads
  -> engine orchestrator
  -> source storage
  -> fast raw segment index
  -> draft compiler
  -> strict validator
  -> approval-to-Git
  -> hybrid permission-aware query
```

Core rule:

```text
ingest creates searchable evidence and drafts
approve creates Git truth
```

## Non-Negotiable Rules

- No fallback/demo pages from empty connector results.
- No LLM fallback stub pages.
- No direct Git commit during ingestion.
- No draft is queryable as official truth by default.
- No generated page is approved without strict YAML/page validation.
- No proposition is trusted without source segment evidence.
- No unauthorized evidence is sent to the answer LLM.
- Classifier and clusterer stay, but they are enrichment/linking tools, not the page authoring path.

## Phase 1: Engine Models And Contracts

Create the language of the new engine before building storage or connectors.

Add:

```text
phase-2/backend/app/ingestion/engine_models.py
```

Define simple dataclasses or Pydantic models:

```text
NormalizedSourceObject
NormalizedSourceDocument
NormalizedSourceSegment
NormalizedSourceRelationship
NormalizedSourceBundle
EngineIngestResult
EngineStageResult
DraftCompileResult
ApprovalResult
```

Minimum fields:

```text
NormalizedSourceObject
- tenant_id
- connector_type
- external_id
- object_type
- title
- url
- author
- created_at
- updated_at
- raw_json
- content_hash
- metadata

NormalizedSourceDocument
- source_object_external_id
- title
- body_text
- metadata
- content_hash

NormalizedSourceSegment
- document_ref
- segment_type
- heading_path
- position
- text
- author
- timestamp
- metadata
- content_hash

NormalizedSourceRelationship
- from_external_id
- to_external_id
- relationship_type
- metadata
```

Tests:

```text
test_normalized_bundle_rejects_empty_documents
test_source_segment_requires_text_and_position
test_engine_result_reports_stage_counts
```

## Phase 2: Engine Orchestrator

Add:

```text
phase-2/backend/app/ingestion/engine.py
```

The orchestrator owns order and policy only.

Initial interface:

```python
class CortexNewEngine:
    def ingest_bundle(self, tenant_id: str, bundle: NormalizedSourceBundle) -> EngineIngestResult:
        ...

    def approve_draft(self, tenant_id: str, draft_id: str, approver: str) -> ApprovalResult:
        ...
```

`ingest_bundle()` flow:

```text
validate non-empty bundle
store source objects/documents/segments/relationships
index raw source segments
compile page drafts
validate drafts
store draft statuses
return counts and failures
```

`approve_draft()` flow:

```text
load draft
run strict validation again
write approved Markdown page
commit page to Git
index approved page
return commit/page metadata
```

Tests:

```text
test_engine_fails_empty_bundle_without_fallback
test_engine_ingest_does_not_commit_to_git
test_engine_returns_counts_for_documents_segments_and_drafts
test_approve_draft_is_the_only_git_commit_path
```

## Phase 3: Source Storage

Add:

```text
phase-2/backend/app/ingestion/source_store.py
```

Update:

```text
phase-2/backend/app/database/models.py
```

Add SQLite tables:

```text
source_objects
source_documents
source_segments
source_relationships
knowledge_page_drafts
propositions
sync_runs
```

Keep schema boring. Use `metadata_json` for connector-specific fields instead of creating many nullable columns.

Important indexes:

```text
source_objects(tenant_id, connector_type, external_id)
source_objects(tenant_id, content_hash)
source_documents(tenant_id, source_object_id)
source_segments(tenant_id, document_id, position)
source_segments(tenant_id, content_hash)
knowledge_page_drafts(tenant_id, status)
propositions(tenant_id, draft_id)
sync_runs(tenant_id, connector_type, started_at)
```

Tests:

```text
test_store_source_object_document_segments_relationship
test_content_hash_skips_unchanged_source_object
test_tenant_a_cannot_read_tenant_b_source_records
test_draft_and_rejected_output_are_not_git_files
```

## Phase 4: Local Upload Adapter

Add:

```text
phase-2/backend/app/ingestion/connectors/base.py
phase-2/backend/app/ingestion/connectors/local_upload.py
```

Adapter contract:

```python
class ConnectorAdapter:
    def discover(self): ...
    def fetch(self): ...
    def extract(self): ...
    def normalize(self) -> NormalizedSourceBundle: ...
```

Local Upload v1 file support:

```text
.md
.txt
.pdf text-only
.docx
.csv
.xlsx
.html
```

Use existing/bundled dependencies where available:

```text
PDF: pypdf or pdfplumber
DOCX: python-docx
CSV/XLSX: pandas/openpyxl
HTML: BeautifulSoup
TXT/MD: stdlib
```

Skip OCR/scanned PDFs in v1 with a clear error.

Tests:

```text
test_local_upload_markdown_preserves_headings
test_local_upload_txt_creates_document_and_segments
test_local_upload_csv_creates_tabular_segments
test_unsupported_binary_file_returns_clear_error
```

## Phase 5: Fast Raw Segment Index

Purpose: make Cortex useful before compilation finishes.

Add:

```text
phase-2/backend/app/retrieval/raw_segment_index.py
```

Use the current `NumPyVectorIndex` pattern first. Do not introduce a new vector DB yet.

Index record IDs should point to source segments, not pages:

```text
segment:{source_segment_id}
```

Flow:

```text
source_segments
  -> embedding
  -> raw_segment_index.json
```

Tests:

```text
test_raw_segment_index_returns_segment_ids
test_raw_segment_index_is_available_before_draft_approval
test_unchanged_segments_are_not_reembedded
```

## Phase 6: Draft Compiler

Add:

```text
phase-2/backend/app/ingestion/compiler.py
phase-2/backend/app/ingestion/propositions.py
phase-2/backend/app/ingestion/drafts.py
```

Compiler input:

```text
source documents + source segments
```

Compiler output:

```text
KnowledgePageDraft
Propositions
Evidence links
Validation status
```

Segmentation strategies:

```text
document_structure: Local Upload, Notion, Google Docs
conversation_thread: Slack
tabular_records: CSV/XLSX later if needed
```

Keep classifier/clusterer optional:

```text
classifier -> label segment/proposition/page
clusterer -> discover related docs, duplicates, conflicts, suggested links
```

Tests:

```text
test_compiler_groups_segments_by_heading_path
test_compiler_creates_draft_not_approved_page
test_proposition_requires_evidence_segment_id
test_classifier_not_required_for_page_creation
test_clusterer_not_required_for_page_creation
```

## Phase 7: Strict Validator

Update:

```text
phase-2/backend/app/ingestion/validation.py
```

Validator must reject:

```text
missing YAML frontmatter
invalid YAML
missing id/title/sources/propositions/synthesis_validation
Input JSON
Expected Output
</output_format>
Based on the provided
markdown fence wrapping entire page
assistant commentary
propositions without evidence_segment_ids
sources that do not exist in source_segments
```

Validation result should be stored, not just raised:

```text
validation_passed
errors
warnings
validated_at
```

Tests:

```text
test_prompt_leakage_rejected
test_invalid_yaml_rejected
test_missing_evidence_rejected
test_unknown_source_segment_rejected
test_valid_evidence_linked_page_passes
```

## Phase 8: Approval-To-Git

Update:

```text
phase-2/backend/app/storage/git_store.py
phase-2/backend/app/api/routes.py
```

Add endpoints:

```text
GET /v1/drafts
GET /v1/drafts/{draft_id}
POST /v1/drafts/{draft_id}/approve
POST /v1/drafts/{draft_id}/reject
```

Approval rules:

```text
DRAFT/PENDING/REJECTED stay in SQLite/storage
APPROVED writes Markdown to tenant Git repo
APPROVED commits one page file
APPROVED indexes page
```

Tests:

```text
test_ingestion_does_not_commit_draft
test_approve_valid_draft_commits_to_git
test_approve_invalid_draft_fails_without_commit
test_rejected_draft_is_not_queryable_as_truth
```

## Phase 9: Notion Normalization

Update:

```text
phase-2/backend/app/ingestion/notion.py
```

Current behavior returns raw message dicts. Replace or wrap it so Notion produces:

```text
NormalizedSourceObject for page/database
NormalizedSourceDocument for page content
NormalizedSourceSegment for blocks/sections
NormalizedSourceRelationship for child pages, database rows, backlinks if available
```

Notion must:

```text
discover accessible pages/databases
fetch block children recursively
preserve headings, paragraphs, bullets, code, tables, callouts, child pages
fail loudly if zero pages are fetched
never produce demo fallback content
```

Tests:

```text
test_notion_normalize_page_to_source_document
test_notion_blocks_become_source_segments
test_notion_empty_sync_fails_without_fallback
test_notion_table_blocks_preserved
```

## Phase 10: Slack And Google Docs

Add:

```text
phase-2/backend/app/ingestion/connectors/slack.py
phase-2/backend/app/ingestion/connectors/google_docs.py
```

Slack:

```text
channel/thread -> SourceDocument
message/reply -> SourceSegment
thread/reply relationship -> SourceRelationship
metadata_json: channel, thread_ts, user, reactions, files
```

Google Docs:

```text
doc -> SourceObject + SourceDocument
heading/paragraph/table -> SourceSegment
doc links/comments if available -> SourceRelationship
metadata_json: heading level, paragraph style, table info
```

Tests:

```text
test_slack_thread_becomes_document
test_slack_messages_become_ordered_segments
test_google_doc_headings_become_heading_paths
test_google_doc_table_rows_preserved
```

## Phase 11: Hybrid Permission-Aware Query

Add:

```text
phase-2/backend/app/retrieval/permissions.py
phase-2/backend/app/retrieval/hybrid_query.py
```

Query should retrieve:

```text
approved pages
propositions
raw source segments
graph neighbors
vector fallback results
```

Then filter before LLM:

```text
user.department
user.role
user.clearance_level
segment.department
segment.access_level
proposition.sensitivity
source_permissions_json
```

Response shape:

```json
{
  "answer": "...",
  "citations": [],
  "pages_read": [],
  "source_segments_read": [],
  "redactions": [],
  "knowledge_gaps": [],
  "confidence": 0.0,
  "latency_ms": 0
}
```

Tests:

```text
test_query_uses_raw_segments_when_no_approved_pages_exist
test_query_uses_approved_pages_and_source_segments
test_unauthorized_segment_not_sent_to_llm
test_query_response_includes_citations_and_knowledge_gaps
```

## Phase 12: API And UI Wiring

Backend endpoints:

```text
POST /v1/uploads
POST /v1/connectors/{connector_type}/sync
GET /v1/sync-runs/{sync_run_id}
GET /v1/source-objects
GET /v1/source-documents/{document_id}
GET /v1/drafts
POST /v1/drafts/{draft_id}/approve
POST /v1/drafts/{draft_id}/reject
POST /v1/query
```

Frontend screens can come after backend is stable:

```text
Upload source
Connector sync status
Source explorer
Draft approval inbox
Query answer with citations
```

Do not build fancy UI before the backend engine works.

## Phase 13: Metrics, Evals, And High Tests

Add evaluation harness:

```text
phase-2/backend/tests/test_new_engine_end_to_end.py
phase-2/backend/tests/test_new_engine_permissions.py
phase-2/backend/tests/test_new_engine_eval.py
```

Metrics to track:

```text
fallback_page_count = 0
prompt_leakage_count = 0
malformed_approved_pages = 0
evidence_link_rate >= 95%
citation_correctness >= 85%
detail_retention_score >= 75%
hallucination_rate <= 5%
time_to_first_searchable_result < 30 seconds
unchanged_documents_skipped >= 80%
```

High test scenarios:

```text
empty source sync
local upload -> raw index -> draft -> approve -> query
Notion page -> segments -> draft -> no fallback
Slack thread -> conversation document -> cited answer
permission denied evidence never reaches answer model
invalid LLM output is rejected and not committed
repeat sync skips unchanged content
```

## Implementation Order

Build in this exact order:

```text
1. engine models/contracts
2. engine orchestrator
3. source storage
4. local upload adapter
5. fast raw segment index
6. draft compiler
7. strict validator
8. approval-to-Git
9. Notion normalization
10. Slack/Google Docs
11. hybrid permission-aware query
12. API/UI wiring
13. evals and high tests
```

## Files Most Likely To Change

```text
phase-2/backend/app/database/models.py
phase-2/backend/app/ingestion/engine_models.py
phase-2/backend/app/ingestion/engine.py
phase-2/backend/app/ingestion/source_store.py
phase-2/backend/app/ingestion/compiler.py
phase-2/backend/app/ingestion/propositions.py
phase-2/backend/app/ingestion/drafts.py
phase-2/backend/app/ingestion/validation.py
phase-2/backend/app/ingestion/notion.py
phase-2/backend/app/ingestion/connectors/base.py
phase-2/backend/app/ingestion/connectors/local_upload.py
phase-2/backend/app/ingestion/connectors/slack.py
phase-2/backend/app/ingestion/connectors/google_docs.py
phase-2/backend/app/retrieval/raw_segment_index.py
phase-2/backend/app/retrieval/permissions.py
phase-2/backend/app/retrieval/hybrid_query.py
phase-2/backend/app/storage/git_store.py
phase-2/backend/app/api/routes.py
```

## What Is Removed Or Disabled

Remove from the main authoring path:

```text
sentence splitting as the core unit
classifier as mandatory first stage
clusterer as page creator
page per sentence cluster
auto Git commit during ingestion
fallback/demo page generation
LLM fallback stub pages
committing drafts to Git
querying drafts as truth
sending unauthorized evidence to LLM
```

Keep but demote:

```text
classifier -> enrichment labels
clusterer -> links, duplicates, conflicts, related pages
```

## Definition Of Done

The new engine is done when:

```text
local upload can ingest and search raw segments
Notion produces normalized source records
Slack and Google Docs adapters produce normalized bundles
drafts are compiled with evidence-linked propositions
invalid drafts are rejected
only approved drafts are committed to Git
query returns cited answers
permission filtering happens before LLM answer generation
high tests pass
eval shows Cortex beats baseline RAG on citation correctness and detail retention
```

