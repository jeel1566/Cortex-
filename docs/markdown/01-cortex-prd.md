Cortex
Product Requirements Document  ·  v1.0  ·  May 2026

What:  Cortex is a knowledge OS that turns scattered company data into structured, agent-readable pages
Why:  AI agents cannot operate on raw scattered data — they need structured executable knowledge
YC Reference:  Summer 2026 RFS by Tom Blomfield — company brain as missing primitive

# 1. Problem
Every company has critical knowledge scattered across Slack, tickets, docs, emails, and people's heads. AI agents cannot operate on that. The models are now good enough. The blocker is structured, executable domain knowledge.
Existing solutions fail: RAG chunks lose context, wikis go stale, chatbots hallucinate policy. Nobody has built the layer between raw company data and reliable AI automation.

# 2. Solution
Cortex ingests raw company data, structures it into a living knowledge graph of executable pages, and exposes it via REST API and MCP. Any AI agent — Claude, GPT, Cursor, Claude Code — queries it and gets complete, accurate, sourced answers in under 200ms.
Not a search engine. Not a chatbot. The structured skills file every AI agent needs to operate a company reliably.

# 3. Core Concept — The Book
Company knowledge is structured like a book. Master index → chapters → pages → linked pages. Each page covers exactly one decision or process. Pages link to related pages. Agents navigate by reading the index, finding the entry page, following primary links always, following conditional secondary links when the question matches.
No chunking. No lost context. Full pages. Transparent traversal path every time.

# 4. Users and Use Cases

# 5. Core Features
## 5.1 Auto-Ingestion Pipeline
Connects to Slack, Notion, Zendesk, GitHub, Google Drive via OAuth and webhooks
Filters junk — removes duplicates, short messages, calendar invites (saves 60-70% LLM cost)
Speech-act classification — labels sentences as CONDITION, PRESCRIPTION, PROCEDURE, EXCEPTION, OUTCOME
Decision-unit clustering — groups sentences into one page per answerable question
LLM synthesis — writes one canonical page per cluster with all source propositions included
Synthesis validation — checks proposition coverage, hallucination rate, completeness score
PII filtering — strips names, emails, phones, SSNs before any LLM sees data
Content-hash deduplication — never re-processes unchanged content

## 5.2 Knowledge Graph
Every page has primary links — always follow when reading this page
Every page has conditional secondary links — follow only if question matches condition
Two-phase BFS traversal — primary links exhausted first, secondary by priority within time budget
Visited-page tracking — prevents infinite loops
Conflict detection — four types: temporal, contextual, specificity, genuine error
Version control — Git repository, every change is a commit with diff and reason

## 5.3 Authority and Permissions
Six authority levels L0 (public) to L5 (owner) for both agents and humans
Claim-level sensitivity — individual propositions tagged, not just whole pages
Most restrictive wins with admin override — confidential source does not poison public claims
Scoped JWT tokens — agents only read what their token explicitly allows

## 5.4 Retrieval API and MCP
REST API — POST /v1/query, GET /v1/page/:id, POST /v1/ingest, POST /v1/feedback
MCP server — query_knowledge, get_page, list_pages tools for AI agent consumption
Under 200ms total retrieval using local fastembed embeddings
Returns pages plus full traversal path plus conflict flags plus confidence score

## 5.5 Evaluation and Feedback
Ground truth evaluation set — 50 real questions, verified human answers, honest RAG comparison
Synthesis validation scores stored on every page — proposition coverage, hallucination rate, completeness
Feedback endpoint — agents flag wrong answers, routes to re-synthesis queue
Observability — query metrics, stale page detection, conflict resolution rate

# 6. Business Model

Day 1 onboarding cost:  Under $50 (500 pages × one LLM synthesis call each)
Daily running cost:  Under $1 (10-20 proposition changes per day)
Query cost:  $0 — agents read pre-built pages directly
Target margin:  $470 gross margin per cloud company per month

# 7. Success Metrics

# 8. What We Are Not Building in MVP
Process mining from Slack — requires structured event logs we do not have yet. Version 2.
DeBERTa-v3 model hosting — use LLM API calls instead. Faster, cheaper at MVP scale.
Zendesk and Google Drive connectors — Slack and GitHub enough to validate.
PostgreSQL — SQLite works to 50k pages. No migration until first enterprise customer.
Celery + Redis queue — synchronous ingestion works at MVP scale.
Cloud hosting — local or single VM until first paying customer.

### Table
User | Core problem | What Cortex does | Example query
Enterprise teams | AI agents give wrong answers about company policy | Structures policies and processes into agent-readable pages | What is our refund policy for VIP customers?
Developers with Claude Code / Cursor | Context lost between coding sessions | Commits, PRs, ADRs become queryable knowledge pages | Why was the auth module refactored in January?
Solo founders | Five AI tools, no shared context | One knowledge base every agent reads | What is my product positioning for the enterprise segment?
Product teams | Decisions forgotten, new members lost | Every meeting decision becomes a searchable page | Why did we drop feature X from the roadmap?
Researchers and journalists | Sources and findings scatter over months | Links findings, surfaces contradictions automatically | Which sources corroborate the Q3 fraud claim?
Legal and compliance | Regulations complex, overlapping, changing | Regulations as pages, conflicts flagged automatically | Does this campaign violate GDPR Article 7?
Open source projects | Institutional knowledge lost when contributors leave | Preserves why decisions were made, not just what | Why was this API design chosen over issue 1247?
Students and learners | Knowledge learned early gets forgotten | Personal knowledge OS that compounds over time | How does attention relate to information retrieval?



### Table
Tier | Price | Who | What
Open source self-hosted | Free | Developers, small teams, open source projects | Full codebase, self-managed. Builds trust and ecosystem.
Cloud hosted | $500/month per company | SMB and mid-market | Managed ingestion, hosting, updates. Flat pricing — no per-query tax.
Enterprise | $2k-10k/month | Large enterprises, legal, compliance | On-premise, SLA, SSO, RBAC, audit logs, dedicated support.



### Table
Metric | Target | When
Agent accuracy on company knowledge vs RAG | >90% on 50-question ground truth set | Before first demo
Total retrieval latency | <200ms p99 | At launch
Initial onboarding time | <1 day for first 500 pages | At launch
Monthly recurring revenue | $10k MRR | Month 6
Paying companies | 10 | Month 6
Pages under management | 50,000 | Month 12
Feedback-triggered re-synthesis rate | <5% of queries flagged | Month 3

