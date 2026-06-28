# Tasks: Notion Ingestion & Page Validation Fixes

**Input**: Design documents from `/specs/002-notion-ingestion-fixes/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Verify git branch is `002-notion-ingestion-fixes` and environment variables are loaded

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core database schema setup that MUST be complete before user stories can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Add the `notion_objects` database model in `phase-2/backend/app/database/models.py`
- [X] T003 Apply SQLite database migrations or recreate DB for testing `phase-2/backend/app/database/connection.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Accurate Notion Ingestion Crawler (Priority: P1) 🎯 MVP

**Goal**: Index Notion documents recursively, compile block hierarchies, and fail sync jobs loudly on empty crawls.

**Independent Test**: Trigger a Notion sync job with empty/unshared Notion integration credentials, verify the job is marked `failed` with 0 pages found, and check that standard Markdown sections are generated for successfully crawled pages.

### Tests for User Story 1

- [X] T004 [P] [US1] Create unit tests for Notion block crawling and fallback removal in `phase-2/backend/tests/test_notion_crawler.py`

### Implementation for User Story 1

- [X] T005 [US1] Implement recursive blocks retrieval in `phase-2/backend/app/ingestion/notion.py`
- [X] T006 [US1] Update `phase-2/backend/app/ingestion/pipeline.py` to record Notion crawling objects in `notion_objects`
- [X] T007 [US1] Update sync endpoints in `phase-2/backend/app/api/routes.py` to fail loudly and return an error if Notion sync fetches 0 documents

**Checkpoint**: User Story 1 is functional. Notion pages fetch children recursively and empty syncs fail loudly.

---

## Phase 4: User Story 2 - Notion Access Check UI (Priority: P2)

**Goal**: Display accessible page counts, sync status, and errors in the dashboard.

**Independent Test**: Load Settings page, click Notion connection check, and verify the list of page titles and databases shown matches SQLite data.

### Implementation for User Story 2

- [X] T008 [P] [US2] Implement metrics/status query routes in `phase-2/backend/app/api/routes.py`
- [X] T009 [US2] Create Notion Access Check settings screen in `phase-2/frontend/app/settings/notion/page.tsx`

**Checkpoint**: Notion Access Check UI is active. Discovered pages list shows in settings.

---

## Phase 5: User Story 3 - Strict Output Gate and YAML Validation (Priority: P1)

**Goal**: Scan generated pages for valid frontmatter and blacklist prompt leakage before saving.

**Independent Test**: Synthesize a page with prompt-leaked substrings (like `</output_format>`). Verify the validator throws an error, rejects the save, and prevents a git commit.

### Tests for User Story 3

- [X] T010 [P] [US3] Create tests for pre-save validation and prompt leakage checking in `phase-2/backend/tests/test_strict_validator.py`

### Implementation for User Story 3

- [X] T011 [US3] Implement `verify_page_shape` function in `phase-2/backend/app/ingestion/validation.py`
- [X] T012 [US3] Integrate pre-save validation gate into `phase-2/backend/app/ingestion/pipeline.py`

**Checkpoint**: Strict validation gate is active. Rejected drafts are never saved or committed to Git.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Performance verification, logging review, and documentation updates.

- [X] T013 Update API documentation and user guide in `README.md`
- [X] T014 Run validation suite using the instructions in `specs/002-notion-ingestion-fixes/quickstart.md`
