# Implementation Plan: Phase 2 — Make it Complete

**Branch**: `001-phase-2-complete` | **Date**: 2026-06-17 | **Spec**: [spec.md](file:///D:/Cortex/specs/001-phase-2-complete/spec.md)

**Input**: Feature specification from `specs/001-phase-2-complete/spec.md`

---

## Summary
The goal of Phase 2 is to elevate the single-tenant local Cortex prototype into a complete, secure, and production-ready multi-tenant Knowledge OS. This involves:
1. Git-versioned page store per tenant.
2. SQLite databases, vector indices, and Git repos partitioned per tenant.
3. FastAPI backend exposing endpoints for `/v1/query`, `/v1/page/:id`, `/v1/ingest`, and `/v1/feedback`.
4. JWT authorization integration using Clerk with L0-L5 authority levels.
5. Ingestion queuing (immediate, standard, background) with a Notion polling connector.
6. A Next.js frontend UI displaying an Admin Approval Inbox and a Knowledge Explorer.

---

## Technical Context

- **Language/Version**: Python 3.11+ (Backend), Node.js v20+ / React (Frontend)
- **Primary Dependencies**: FastAPI, Uvicorn, GitPython, SQLite3, FastEmbed, Pytest, Next.js, Clerk SDK, TailwindCSS
- **Storage**: SQLite (separate database file per tenant), Git (local repository directory per tenant), JSON-based NumPyVectorIndex (or local index files per tenant)
- **Testing**: Pytest with unit and integration coverage.
- **Target Platform**: Single VM deployment / Local localhost server (MVP scale)
- **Project Type**: Web Service (FastAPI backend + Next.js frontend + local directories)
- **Performance Goals**: Retrieval & graph traversal latency < 150ms p95; database querying < 20ms.
- **Constraints**: Pure physical tenant isolation of data; authorization gates enforced on all query paths.
- **Scale/Scope**: Supporting up to 10 distinct tenants, up to 50k knowledge pages per tenant.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Rule 1: Local & Fast Execution** -> Cosine similarity index and SQLite lookups run completely locally using local fastembed.
- **Rule 2: Version Control & Auditability** -> Transition from a flat pages directory to a `GitPython`-managed Git repository per tenant.
- **Rule 3: Synthesis Validation** -> Maintain proposition coverage, hallucination rate, and completeness scores in the YAML header of every page.
- **Rule 4: Technology Stack Constraints** -> Backend uses Python/FastAPI/SQLite, Frontend uses Next.js with Clerk auth.

All core constraints of the constitution are respected. No complexity justifications are needed.

---

## Project Structure

### Documentation (this feature)
```text
specs/001-phase-2-complete/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
└── quickstart.md        # Phase 1 output
```

### Source Code Structure
```text
phase-2/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py         # Clerk JWT verification and L0-L5 authority validation
│   │   │   ├── routes.py       # endpoints: query, page, ingest, feedback
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── connection.py   # Multi-tenant SQLite db connections
│   │   │   ├── models.py       # SQL schemas (tenants, agents, ingestion_jobs, feedback, query_log)
│   │   ├── ingestion/
│   │   │   ├── __init__.py
│   │   │   ├── queue.py        # Ingestion queue worker (immediate, standard, background)
│   │   │   ├── notion.py       # Notion polling connector
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── git_store.py    # GitPython wrapper for tenant git repos
│   │   ├── config.py
│   │   ├── main.py             # FastAPI App entry point
│   ├── tests/
│   │   ├── test_auth.py
│   │   ├── test_isolation.py
│   │   ├── test_feedback.py
│   ├── requirements.txt
│   ├── run_backend.py
│   
├── frontend/
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx
│   │   ├── page.tsx            # Landing/Dashboard
│   │   ├── inbox/              # Admin Approval Inbox
│   │   ├── explorer/           # Knowledge Explorer
│   │   ├── login/
│   ├── components/
│   ├── middleware.ts           # Clerk auth middleware
│   ├── package.json
```

**Structure Decision**: Option 2 (Web application with separate frontend/backend subdirectories) under the `phase-2/` root directory to maintain clean separation of Python and Node/Next.js dependencies.
