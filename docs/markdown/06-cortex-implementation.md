Cortex
Implementation Plan  ·  v1.0  ·  May 2026

Non-negotiable rule: Build ground truth evaluation set on Day 1. Run RAG baseline on Day 1. Do not write any more code until you know Cortex beats RAG on 50 real questions.

# Phase 1 — Prove it works (Week 1)
## Day 1 — Ground truth first

## Day 2 — Embedding module

## Day 3 — Replace stubs with real LLM calls

## Day 4 — Synthesis validation

## Day 5 — Slack connector and first honest benchmark

# Phase 2 — Make it complete (Week 2)

# Phase 3 — Ship it (Week 3)

# Phase 4 — Version 2 (After first paying customer)

### Table
Task | Output | Test
Create eval/ground_truth.json — 50 real questions about a real company with verified human answers | eval/ground_truth.json with 50 Q&A pairs | All 50 questions have verified answers from a human expert
Run LlamaIndex naive RAG on same 50 questions over same documents | eval/rag_baseline.json with 50 answers | RAG can at least attempt all 50 questions
Score RAG baseline 1-5 per answer on accuracy, completeness, source attribution | RAG baseline score | Baseline score recorded honestly



### Table
Task | Output | Test
Create app/llm/embedding.py using fastembed + BAAI/bge-small-en-v1.5 | embedding.py with encode(text) -> vector function | Unit test: encode('hello') returns 384-dim vector in under 30ms
Wire embedding.py into HNSW vector index — populate index when page is created | HNSW index populated on page creation | Integration test: create 10 pages, query HNSW, verify correct page returned
Test end-to-end: POST /v1/query with real question returns a page | Working /v1/query endpoint | Test query returns pages in under 200ms



### Table
Task | Output | Test
Replace classifier stub with DeepSeek call — classify 20 sentences in one batch call | Real speech-act classification working | Test: 'Refunds are processed within 5 days' classified as PRESCRIPTION
Replace clusterer stub with DeepSeek call — cluster a set of classified sentences into decision units | Real clustering working | Test: 10 sentences about refunds cluster into one decision unit
Test ingestion pipeline end-to-end with 5 real documents | 5 pages synthesised correctly | Pages have correct YAML headers and valid content



### Table
Task | Output | Test
Build validation pass: proposition_coverage check — verify every source claim appears in synthesised page | Validation module with coverage check | Test: page missing a source claim fails validation and triggers re-synthesis
Build validation pass: hallucination check — verify every synthesised claim traces to a source | Hallucination check working | Test: page with invented claim fails validation
Build validation pass: completeness score — LLM rates if page answers the original question | Completeness scoring working | Test: incomplete page scores under 7 and triggers re-synthesis
Store validation scores in page YAML header | YAML header includes synthesis_validation block | Test: every page has validation scores after ingestion



### Table
Task | Output | Test
Build Slack connector with OAuth bot token and rate-limit backoff queue | app/connectors/slack.py working | Test: connect to real Slack workspace, pull 100 messages successfully
Run full ingestion on real Slack export from test company | Real pages generated from real data | Pages synthesised with real company knowledge
Run Cortex on 50 ground truth questions, score results | eval/cortex_v1.json with 50 answers | Honest comparison against RAG baseline
If Cortex beats RAG: continue to Phase 2. If not: fix the specific failures first. | Decision point | Cortex must score higher than RAG before moving on



### Table
Day | Task | Output
6 | Convert page store to Git repository per tenant using gitpython | Git-based OS working, every change is a commit
6 | Add claim-level sensitivity scoring — every proposition tagged individually | Propositions have sensitivity levels, permission poison problem solved
7 | Implement agent authority levels L0-L5 with scoped JWTs using Clerk | Auth working end-to-end for all authority levels
7 | Per-tenant isolation — separate HNSW index, graph store, SQLite, Git repo per tenant | Two tenants can run simultaneously without data leakage
8 | Build Notion connector with polling-primary (5-minute polling, not webhook-primary) | Notion ingestion working on real workspace
8 | Build POST /v1/feedback with re-synthesis routing and re-validation | Feedback loop fully closed
9 | Tiered freshness logic — immediate queue, standard 15-min queue, background weekly batch | Freshness working correctly for all tiers
9 | structlog structured logging and Prometheus metrics | Every query logged, latency tracked, stale pages detected
10 | Frontend — Next.js Approval Inbox with Clerk auth | Human can log in and approve/reject changes
10 | Frontend — basic Knowledge Explorer list view (graph visualisation in v2) | Human can browse all pages with status



### Table
Day | Task | Output
11 | GitHub connector with webhook receiver and force-push detection | Developer use case working end-to-end
12 | cortex init CLI tool — developer runs in project root, bootstraps ingestion | Developer can init Cortex in a new project in under 5 minutes
13 | Deploy to single VM. Configure webhook endpoints. Test all flows end-to-end. | Live system accessible from internet
14 | Run full evaluation on deployed system — 50 questions, Cortex vs RAG, honest score | Published benchmark
15 | First customer demo with real company, real data, real questions | Customer feedback recorded



### Table
Feature | When to build | Why waiting
Process mining from Slack and Zendesk behavioral traces | After 3 customers using it for 60+ days | Need structured event log data to make it real. Cannot fake it.
Knowledge Explorer graph visualisation (D3 or Cytoscape) | After approval inbox is validated by users | Visual graph is nice but not needed to prove the product works.
PostgreSQL migration from SQLite | When any tenant exceeds 50,000 pages | SQLite is fine until then. Do not over-engineer.
Celery + Redis async ingestion queue | When concurrent ingestion jobs exceed 5/minute | Synchronous works at MVP. Add queue only when it bottlenecks.
Google Cloud Run or AWS ECS deployment | At first enterprise customer | Single VM fine for first 10 customers.
Zendesk and Google Drive connectors | Based on customer demand | Slack and GitHub prove the concept. Others follow demand.
DeBERTa-v3 for classification (replacing LLM calls) | When classification cost exceeds $100/month | LLM calls work fine at MVP scale and are easier to maintain.
HNSW compaction schedule | When any tenant has over 100,000 pages | Not needed before then.

