Cortex
Technical Requirements Document  ·  v1.0  ·  May 2026

# 1. System Requirements

# 2. Tech Stack — Locked

# 3. Functional Requirements
## FR-1: Ingestion

## FR-2: Storage

## FR-3: Retrieval

## FR-4: Auth and Permissions

## FR-5: Evaluation and Feedback

# 4. Non-Functional Requirements

### Table
Requirement | Value | Non-negotiable?
Total query latency p99 | <200ms including local embedding | Yes
Query embedding latency | <30ms using local fastembed model | Yes
HNSW lookup latency | <5ms for 100k pages | Yes
Graph traversal latency | <50ms for 10 page hops | Yes
Ingestion throughput | 500 pages per hour per tenant | No — v1 target
Page synthesis accuracy | >90% proposition coverage | Yes
Hallucination rate | <2% unsourced claims per page | Yes
PII false positive rate | <1% real knowledge incorrectly stripped | Yes
Uptime SLA (MVP) | 95% — single VM, no HA | No
Uptime SLA (enterprise) | 99.9% — requires v2 infrastructure | No
Max tenants on single VM | 50 companies at MVP scale | No
Max pages per tenant (MVP) | 50,000 pages | No
Max pages per tenant (v2) | 1,000,000 pages | No



### Table
Layer | Technology | Version | Why locked
Language | Python | 3.11+ | FastAPI, hnswlib, fastembed all Python-native
API framework | FastAPI | Latest | Async, auto OpenAPI, already built
LLM synthesis | DeepSeek-V3 via Azure AI Foundry | V3 | Already working in codebase
Local embedding | fastembed + BAAI/bge-small-en-v1.5 | Latest | 10ms local, 384 dims, no API call, no vendor dependency
Vector index | hnswlib | 0.8+ | Already wrapped and unit tested
Graph store | Flat arrays in-memory per tenant | Custom | Already built and tested. Two-phase BFS works.
Page store | Git repository per tenant (gitpython) | Latest | Version control, diff, audit trail for free
Database | SQLite per tenant (MVP) | 3.x | Zero setup, works to 50k pages
Frontend framework | Next.js 14 | 14 | React server components, fast
Frontend auth | Clerk | Latest | Fastest JWT + OAuth for Next.js
Logging | structlog | Latest | Structured JSON logs for observability
Metrics | Prometheus + prometheus-fastapi-instrumentator | Latest | Query latency, page metrics, error rates
Testing | pytest + pytest-asyncio | Latest | Already used in existing tests



### Table
ID | Requirement | Priority
FR-1.1 | System must ingest Slack messages via OAuth and Events API | P0
FR-1.2 | System must ingest GitHub commits and PRs via webhook | P0
FR-1.3 | System must ingest Notion pages via polling every 5 minutes | P1
FR-1.4 | System must filter content before LLM — remove duplicates, short messages, calendar invites | P0
FR-1.5 | System must run PII detection and redaction before any LLM call | P0
FR-1.6 | System must classify sentences into 5 speech act types via LLM | P0
FR-1.7 | System must cluster sentences into decision units — one unit per answerable question | P0
FR-1.8 | System must synthesise one canonical page per cluster with sourced propositions | P0
FR-1.9 | System must validate every synthesised page: proposition coverage >90%, hallucination <2% | P0
FR-1.10 | System must store synthesis validation scores in page YAML header | P0
FR-1.11 | System must detect and classify conflicts into 4 types after synthesis | P1
FR-1.12 | System must route changes through tiered freshness: immediate, standard, background | P1



### Table
ID | Requirement | Priority
FR-2.1 | Each page must be stored as markdown with YAML header in tenant Git repository | P0
FR-2.2 | Every page change must be a Git commit with message, author, and reason | P0
FR-2.3 | Page YAML header must contain: id, title, version, content_hash, owner, last_updated, access_level, primary_links, secondary_links, conflicts, synthesis_validation, change_history, sources | P0
FR-2.4 | Each proposition must be individually tracked with sensitivity level | P1
FR-2.5 | Content hash must be compared before any re-synthesis — unchanged content never re-processed | P0



### Table
ID | Requirement | Priority
FR-3.1 | POST /v1/query must return answer in under 200ms p99 | P0
FR-3.2 | Entry page must be found via local fastembed HNSW lookup | P0
FR-3.3 | Traversal must use two-phase BFS: primary links first, secondary by priority within time budget | P0
FR-3.4 | Visited-page set must prevent traversal loops | P0
FR-3.5 | Response must include: pages, traversal_path, conflicts, confidence, latency_ms | P0
FR-3.6 | Agent must only receive propositions within its authority level scope | P0
FR-3.7 | Knowledge gaps must be surfaced when HNSW similarity below threshold — not hallucinated | P0



### Table
ID | Requirement | Priority
FR-4.1 | Every API request must include valid Bearer JWT token | P0
FR-4.2 | JWT must contain: tenant_id, subject, authority_level (L0-L5), scope, expiry | P0
FR-4.3 | Tokens must expire after 24 hours, refresh tokens valid 30 days | P0
FR-4.4 | Compromised token must be revocable immediately via admin API | P0
FR-4.5 | Permission check must happen at query time, not ingestion time | P0
FR-4.6 | Claim-level sensitivity must be evaluated per-proposition, not per-page | P1
FR-4.7 | Most restrictive wins rule applies unless admin explicitly overrides with audit log entry | P0



### Table
ID | Requirement | Priority
FR-5.1 | Ground truth eval set of 50 questions must exist before first customer demo | P0 — non-negotiable
FR-5.2 | POST /v1/feedback must accept wrong_answer, missing_knowledge, outdated, conflict_missed | P0
FR-5.3 | Feedback must trigger re-synthesis queue for flagged pages | P0
FR-5.4 | Re-synthesis must run validation pass automatically | P0
FR-5.5 | Prometheus metrics must track: query latency, pages queried, pages never queried, feedback rate, synthesis validation scores | P1



### Table
Category | Requirement
Security | All data encrypted at rest (AES-256) and in transit (TLS 1.3)
Security | PII never stored in raw form — always redacted before storage
Security | Per-tenant isolation at every layer — no shared state between tenants
Security | JWT tokens signed with RS256 — asymmetric keys, public key published
Performance | Local embedding model loaded at startup — no cold start per query
Performance | HNSW index loaded in memory per tenant at startup
Performance | Graph adjacency list loaded in memory per tenant at startup
Reliability | All ingestion jobs idempotent — safe to retry on failure
Reliability | Git page store is the source of truth — all other stores can be rebuilt from it
Observability | Every query logged with structured JSON including latency, pages read, tenant, authority level
Observability | All errors logged with stack trace, tenant, and request ID
Maintainability | Every function under 50 lines — single responsibility
Maintainability | Unit test coverage above 80% for ingestion pipeline and traversal engine

