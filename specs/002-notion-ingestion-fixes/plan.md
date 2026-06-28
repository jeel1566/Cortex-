# Implementation Plan: Notion Ingestion & Page Validation Fixes

**Branch**: `002-notion-ingestion-fixes` | **Date**: 2026-06-28 | **Spec**: [spec.md](file:///D:/Cortex/specs/002-notion-ingestion-fixes/spec.md)

**Input**: Feature specification from `/specs/002-notion-ingestion-fixes/spec.md`

---

## Summary
The goal of this feature is to address structural failures in the ingestion pipeline and Notion connector:
1. **Remove silent fallback**: If Notion sync returns zero documents or errors, fail the ingestion job with a clear description, instead of silently creating demo pages.
2. **Implement full Notion document ingestion**: Build a 3-step crawler (Discover, Extract, Compile) fetching page block children recursively to assemble complete raw `SourceDocument` objects. Chunk them by headers/sections rather than sentence clusters.
3. **Strict pre-save validator**: Enforce a strict schema gate rejecting pages with prompt leakage (e.g. "Expected Output", "</output_format>"). Ensure only valid, structured Markdown pages starting with a valid YAML frontmatter are committed to Git.
4. **Notion Access Check UI**: Show connected Notion pages, databases, and sync metrics in the dashboard.

---

## Technical Context

- **Language/Version**: Python 3.11+ (Backend), Node.js v20+ / React / Next.js (Frontend)
- **Primary Dependencies**: FastAPI, Notion-Client, Pydantic, GitPython, SQLite3, Pytest
- **Storage**: SQLite (`notion_objects` registry table per tenant), Git (local repositories per tenant)
- **Testing**: Pytest with mocked Notion API block payloads and custom LLM synthesis payloads.
- **Target Platform**: Local localhost server / Single VM
- **Project Type**: Web Service (FastAPI backend + Next.js frontend)
- **Performance Goals**: Notion crawling recursive block extraction under 5 seconds for normal-sized pages (up to 100 blocks). Validation checks under 50ms.
- **Constraints**: Tenant physical data isolation must be preserved. Rejecting validation errors must prevent Git commits.
- **Scale/Scope**: Up to 10 tenants, crawls up to 500 pages per workspace.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Rule 1: Structured Knowledge over Raw Chunks** -> We transition from sentence clustering to section/heading-based chunking. Recursive block extraction preserves Notion page formatting (headings, code blocks, bullet lists).
- **Rule 2: Local & Fast Execution** -> YAML parsing and regex-based prompt-leak scanning run locally in Python without LLM overhead.
- **Rule 3: Strict Ingestion Filtering** -> Stop generating fake demo data on sync failures. Fail loudly to save LLM synthesis API costs.
- **Rule 4: Synthesis Validation & Verification** -> Implement a pre-save validator enforcing YAML frontmatter structure and checking for prompt-leak phrases.
- **Rule 5: Version Control & Auditability** -> Git commits are only performed for validated, approved pages. No malformed drafts or stubs are ever committed to Git.

All rules are fully respected. No complexity justifications are needed.

---

## Project Structure

### Documentation (this feature)
```text
specs/002-notion-ingestion-fixes/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (created by speckit-tasks)
```

### Source Code Layout (Modified Paths)
```text
phase-2/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes.py       # API endpoints (add sync metadata overview route)
│   │   ├── database/
│   │   │   ├── models.py       # Add NotionObject SQLite model
│   │   ├── ingestion/
│   │   │   ├── notion.py       # Notion block crawler (Discover/Extract)
│   │   │   ├── pipeline.py     # Ingestion compiler and strict pre-save validator
│   │   │   ├── synthesizer.py  # Header-based chunking and improved prompt context
│   │   │   ├── validation.py   # Validation scores and shape verification
│   └── tests/
│       ├── test_notion_crawler.py  # Crawling and block recursive extraction test
│       ├── test_strict_validator.py # Pre-save validation tests
│   
├── frontend/
│   ├── app/
│   │   ├── settings/
│   │   │   ├── notion/
│   │   │   │   ├── page.tsx    # Notion Access Check and Sync metrics dashboard
```

**Structure Decision**: Web application layout matching the existing Phase 2 multi-tenant structure.

---

## Complexity Tracking

> No violations of the Cortex Constitution.
