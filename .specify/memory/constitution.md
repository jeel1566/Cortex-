<!--
Sync Impact Report:
- Version change: None (Initial Constitution) -> 1.0.0
- List of modified principles:
  * [PRINCIPLE_1_NAME] -> I. Structured Knowledge over Raw Chunks
  * [PRINCIPLE_2_NAME] -> II. Local & Fast Execution
  * [PRINCIPLE_3_NAME] -> III. Strict Ingestion Filtering & Cost Control
  * [PRINCIPLE_4_NAME] -> IV. Synthesis Validation & Verification
  * [PRINCIPLE_5_NAME] -> V. Version Control & Auditability
- Added sections:
  * Technology Stack Constraints
  * Development Workflow & Quality Gates
- Removed sections: None
- Templates requiring updates:
  * .specify/templates/plan-template.md (✅ updated)
  * .specify/templates/spec-template.md (✅ updated)
  * .specify/templates/tasks-template.md (✅ updated)
- Follow-up TODOs: None
-->

# Cortex Constitution

## Core Principles

### I. Structured Knowledge over Raw Chunks
Company knowledge must be structured like a book (Index -> Chapters -> Pages) rather than fragmented arbitrary text chunks. Every page covers exactly one answerable decision or process with explicit links, ensuring zero lost context during agent traversal.

### II. Local & Fast Execution
The core retrieval and embedding engine must execute locally and synchronously to ensure a total retrieval latency under 200ms p99. Use fastembed with BAAI/bge-small-en-v1.5 and a local SQLite database to prevent network overhead and third-party API dependencies for search operations.

### III. Strict Ingestion Filtering & Cost Control
Filter raw inputs ruthlessly (skipping messages under 20 words, duplicates, bot messages, calendar invites) before running LLM synthesis. Deduplicate using content hashes to minimize LLM synthesis calls and onboarding/running costs.

### IV. Synthesis Validation & Verification
All generated knowledge pages must pass structured LLM-based verification checks, including proposition coverage (>= 90%), hallucination rate (<= 2%), and completeness (score >= 7/10). No hallucinated or unsourced information is allowed to persist.

### V. Version Control & Auditability
All knowledge pages must be stored in a Git repository. Every update, creation, or feedback-triggered change must be committed programmatically with a clear message and diff, establishing a transparent history of page progression.

## Technology Stack Constraints

- **Language**: Python 3.11+
- **API Framework**: FastAPI
- **Database**: SQLite for MVP (up to 50k pages)
- **Vector Index**: hnswlib / local fastembed (BAAI/bge-small-en-v1.5)
- **LLM API**: DeepSeek-V3 via Azure AI Foundry
- **Hosting**: Local VM or single instance for MVP
- **Frontend**: Next.js 14 with Clerk for Auth

## Development Workflow & Quality Gates

- **Test Coverage**: All core modules (embeddings, classifier, slack/github connectors, synthesis validation, retrieval routes) must have comprehensive unit/integration tests using pytest and mocked API responses.
- **PII Filtering**: Strip names, emails, phones, and SSNs before data is passed to any external LLM.
- **Feedback Loop**: Enable query logging and post-query feedback routes to flag inaccurate or outdated pages, automatically routing them back to the ingestion pipeline for re-synthesis.

## Governance

- The Cortex Constitution is the single source of truth for engineering practices and architectural rules.
- Any modifications to the core principles require updating this file, incrementing the version, and ensuring that all templates stay in sync.
- All code changes must align with the performance (200ms latency), testing, and validation rules specified here.

**Version**: 1.0.0 | **Ratified**: 2026-06-08 | **Last Amended**: 2026-06-08
