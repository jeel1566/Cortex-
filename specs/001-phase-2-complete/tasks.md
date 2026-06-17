# Tasks: Phase 2 — Make it Complete

**Input**: Design documents from `/specs/001-phase-2-complete/`

**Prerequisites**: plan.md (required), spec.md (required)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and folder structure setup.

- [X] T001 Create backend and frontend folder structure under `phase-2/`
- [X] T002 Initialize python requirements in `phase-2/backend/requirements.txt`
- [X] T003 [P] Configure next.js package.json in `phase-2/frontend/package.json`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database, config, and logging foundation.

- [X] T004 Implement SQLite database models schema in `phase-2/backend/app/database/models.py`
- [X] T005 Implement tenant metadata store connection pooler in `phase-2/backend/app/database/connection.py`
- [X] T006 [P] Configure global config settings in `phase-2/backend/app/config.py`
- [X] T007 [P] Implement structured JSON logging via `structlog` in `phase-2/backend/app/logging.py`

---

## Phase 3: User Story 1 - Git-backed Version Control & Sensitivity Tagging (Priority: P1) 🎯 MVP

**Goal**: Track every knowledge page update in a local Git repository per tenant, and tag claim propositions with sensitivity clearance levels.

**Independent Test**: Ingest a set of messages, inspect the YAML header of the page to check sensitivity tags, and verify that a git commit has been automatically created in the tenant's git repository.

### Implementation for User Story 1
- [X] T008 [P] [US1] Create git repository initialization and commit wrapper using `gitpython` in `phase-2/backend/app/storage/git_store.py`
- [X] T009 [US1] Modify parser to inject sensitivity tags (`public` | `team` | `confidential`) into propositions in `phase-2/backend/app/ingestion/synthesizer.py`
- [X] T010 [US1] Update the ingestion compiler pipeline to execute a git commit on page update in `phase-2/backend/app/ingestion/pipeline.py`
- [X] T011 [P] [US1] Write unit tests checking YAML sensitivity tags and git commits in `phase-2/backend/tests/test_git_sensitivity.py`

---

## Phase 4: User Story 2 - Multi-Tenant Isolation & Clerk Authorization (Priority: P1)

**Goal**: Partition SQLite, Git, and HNSW indices strictly per tenant and enforce JWT scopes on query paths.

**Independent Test**: Query the endpoint under tenant A and verify zero bleed from tenant B. Execute query using a low-clearance JWT and verify 403 Forbidden.

### Implementation for User Story 2
- [X] T012 [P] [US2] Implement Clerk JWT decode and public key signature validation logic in `phase-2/backend/app/api/auth.py`
- [X] T013 [US2] Create FastAPI middleware to assert tenant ID isolation and check L0-L5 authority levels in `phase-2/backend/app/api/auth.py`
- [X] T014 [US2] Add isolated routing paths for POST `/v1/query` and GET `/v1/page/:id` in `phase-2/backend/app/api/routes.py`
- [X] T015 [P] [US2] Write tests verifying multi-tenant isolation and authority validation gates in `phase-2/backend/tests/test_auth_isolation.py`

---

## Phase 5: User Story 3 - Notion Connector & Feedback Loops (Priority: P2)

**Goal**: Add support for importing documents from Notion every 5 minutes and building feedback resynthesis paths.

**Independent Test**: Trigger the polling job to fetch edit differences from Notion, and submit a page correction via `/v1/feedback` to trigger re-synthesis.

### Implementation for User Story 3
- [X] T016 [P] [US3] Implement Notion client API wrapper fetching document logs in `phase-2/backend/app/ingestion/notion.py`
- [X] T017 [US3] Implement standard polling job queue scheduler (5-minute polling) in `phase-2/backend/app/ingestion/queue.py`
- [X] T018 [US3] Add POST `/v1/feedback` route to trigger re-synthesis and validation passes in `phase-2/backend/app/api/routes.py`
- [X] T019 [P] [US3] Write integration tests for Notion polling and feedback routing in `phase-2/backend/tests/test_notion_feedback.py`

---

## Phase 6: User Story 4 - Admin Approval Inbox UI (Priority: P2)

**Goal**: Build a Next.js web application display enabling moderators to review proposed drafts and search all pages.

**Independent Test**: Load the dev server, log in using Clerk, view a draft page, click approve, and check database updates.

### Implementation for User Story 4
- [X] T020 [P] [US4] Setup Next.js page layout, navigation, and Clerk Auth provider integration in `phase-2/frontend/app/layout.tsx`
- [X] T021 [US4] Implement Admin Approval Inbox dashboard route displaying pending drafts in `phase-2/frontend/app/inbox/page.tsx`
- [X] T022 [P] [US4] Implement list-based Knowledge Explorer page listing all pages in `phase-2/frontend/app/explorer/page.tsx`
- [X] T023 [US4] Add frontend Clerk middleware to protect admin inbox and explorer routes in `phase-2/frontend/middleware.ts`

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Performance, metrics, and deployment documentation.

- [X] T024 Integrate Prometheus metrics handler and registry in `phase-2/backend/app/main.py`
- [X] T025 Add API endpoints rate limiting in `phase-2/backend/app/api/routes.py`
- [X] T026 Update setup instructions and configuration parameters in `phase-2/README.md`

---

## Dependencies & Execution Order

### Phase Dependencies
- **Phase 1 (Setup)**: Initial setup block.
- **Phase 2 (Foundational)**: Prerequisite for all API operations.
- **Phase 3 (User Story 1)**: First MVP increment.
- **Phase 4, 5, 6**: Can run in parallel after Phase 2 is complete.

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Setup and Foundational blocks (T001 - T007).
2. Complete Phase 3 (US1 - Git page store and sensitivity tagging).
3. Validate and verify US1.
