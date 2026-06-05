Cortex
Architecture Document  ·  v1.0  ·  May 2026

# 1. System Architecture Overview
Cortex is a six-layer system. Each layer has a single responsibility. No layer knows the internal implementation of another layer. All communication is through defined interfaces.

# 2. Data Flow Architecture
## Ingestion path
Source event
    ↓
Connector normalises to IngestionEvent { source, content, author, timestamp, authority_score }
    ↓
Filter pass — remove junk (60-70% eliminated, zero LLM cost)
    ↓
PII filter — Presidio redacts names, emails, phones, SSNs
    ↓
Classify pass — DeepSeek labels each sentence: CONDITION | PRESCRIPTION | PROCEDURE | EXCEPTION | OUTCOME
    ↓
Cluster pass — DeepSeek groups sentences into decision units
    ↓
Synthesise pass — DeepSeek writes one canonical page per cluster (one LLM call per page)
    ↓
Validate pass — check proposition_coverage > 90%, hallucination < 2%, completeness > 7/10
    ↓
Conflict detection — compare new pages against existing linked pages
    ↓
Index update — generate fastembed vector, update HNSW, update graph adjacency list
    ↓
Git commit — page written to tenant Git repo with commit message
    ↓
Approval inbox — human reviews significant changes

## Query path
Agent: POST /v1/query { question, time_budget_ms }
    ↓
Auth: decode JWT, verify RS256 signature, extract tenant_id + authority_level + scope
    ↓
Embed: fastembed.encode(question) → 384-dim vector [10-30ms local]
    ↓
HNSW lookup: index[tenant_id].search(vector, k=3) → top-3 candidate page IDs [3ms]
    ↓
Permission filter: remove pages above agent's authority_level
    ↓
Phase 1 traversal: BFS exhaust all primary_links from entry page [0.3ms]
    ↓
Phase 2 traversal: priority queue secondary_links by relevance, consume time budget [0.3ms]
    ↓
Proposition filter: remove propositions above agent's authority_level from each page
    ↓
Assemble: build response with pages, traversal_path, conflicts, confidence [0.1ms]
    ↓
Return: 200 OK [total 13-33ms typical]

# 3. Per-Tenant Isolation

# 4. Agent Authority Architecture

# 5. Synthesis Validation Architecture

# 6. Conflict Detection Architecture

# 7. Git OS Repository Structure
tenants/{tenant_id}/os/
├── index.yaml                    # Master index: topic → page_id mappings
├── pages/
│   ├── page_013.md               # One markdown file per knowledge page
│   ├── page_042.md
│   └── page_055.md
├── graph/
│   ├── adjacency.json            # { page_id: { primary: [...], secondary: [{condition, page}] } }
│   └── conditions.json           # Pre-compiled condition bytecode for VM
├── eval/
│   ├── ground_truth.json         # 50 questions with verified answers
│   └── results.json              # Latest eval run: Cortex vs RAG scores
├── conflicts/
│   └── active.json               # Currently unresolved genuine conflicts
└── .cortex/
    ├── config.yaml               # Tenant config: connectors, access defaults
    └── feedback.json             # Agent feedback queue awaiting re-synthesis

# 8. Timing Proof

### Table
Layer | Responsibility | Technology | Status
1. Source connectors | Pull raw events from company data sources | Slack Events API, GitHub webhooks, Notion polling | 20% — GitHub only
2. Ingestion pipeline | Transform raw events into structured knowledge pages | FastAPI, DeepSeek-V3, Presidio, fastembed | 75% — classifier/clusterer are stubs
3. Page store | Persist pages with version control | Git repo per tenant (gitpython), markdown + YAML | 95% — works, converting to Git
4. Vector index | Enable fast entry-page lookup by semantic similarity | hnswlib, fastembed BAAI/bge-small-en-v1.5 | 60% — HNSW built, embedding missing
5. Graph store | Enable fast link traversal between pages | Flat array adjacency lists, in-memory per tenant | 95% — fully built and tested
6. API and MCP | Expose retrieval to external agents | FastAPI REST, custom MCP layer, Clerk JWT auth | 85% — endpoints work, OAuth not enforced



### Table
Component | Isolation method | Shared?
Git OS repository | Separate directory per tenant: /data/tenants/{tenant_id}/os/ | Nothing shared
HNSW vector index | Separate hnswlib.Index instance per tenant, loaded in memory dict keyed by tenant_id | Nothing shared
Graph store | Separate adjacency list dict per tenant, loaded in memory dict keyed by tenant_id | Nothing shared
SQLite database | Separate file per tenant: /data/tenants/{tenant_id}/cortex.db | Nothing shared
Ingestion pipeline | All pipeline functions take tenant_id as first argument, all paths scoped to tenant | Pipeline code shared, state isolated
API routing | tenant_id extracted from JWT token on every request, all lookups use tenant_id | FastAPI app shared, all data isolated



### Table
Level | Name | Read access | Write access | Token scope
L0 | Public | Public pages only | None | access:public
L1 | Read-only member | Public + team pages | None | access:team
L2 | Contributor | Public + team + department pages | Propose new pages via /v1/ingest | access:department:X write:propose
L3 | Reviewer | All pages in authority scope | Propose + flag conflicts | access:all write:propose flag:conflicts
L4 | Admin agent | All pages | Write + approve minor changes | access:all write:approve:minor
L5 | Owner | Everything including confidential | Full write + full approval | access:all write:all approve:all



### Table
Check | Method | Threshold | Failure action
Proposition coverage | Extract factual claims from sources. Verify each appears in synthesised page. | >90% claims covered | Re-synthesise with explicit prompt to include missing claims
Hallucination detection | Find every claim in synthesised page. Verify each traces to a source document. | <2% unsourced claims | Strip unsourced claims. Flag page if >2 stripped.
Completeness score | LLM rates: given only this page, can you answer the original question? Score 1-10. | Score ≥7 | Re-synthesise with lower temperature and stricter constraints
Stored output | All three scores stored in page YAML: synthesis_validation block | Always stored | Page marked validation_passed: false if any check fails



### Table
Conflict type | How detected | Resolution strategy
Temporal | Two pages contradict AND timestamps differ by >30 days | Newer page is current truth. Older page archived as historical. Timeline shown in UI.
Contextual | Two pages contradict AND each applies to different entity type (VIP vs standard) | Both pages valid. Cross-reference added. Agent returns both with context labels.
Specificity | One page covers a subset of another's entities (enterprise = subset of all customers) | Mark as parent-child. Exception overrides general rule. Primary link added.
Genuine error | Contradiction at same time and context with no differentiating entity type | Both pages flagged. Owner notified. Human resolution required before either page is served.



### Table
Operation | Method | Latency
Query embedding | fastembed local model — no API call | 10-30ms
HNSW entry page lookup | In-memory hnswlib search over 384-dim vectors | 3ms
Primary link traversal (5 hops) | Flat array O(1) lookup × 5 | 0.3ms
Secondary condition evaluation (10 conditions) | Pre-compiled bytecode VM at 100ns each | 0.01ms
Page reads (6 pages) | Memory-mapped flat files or Git object reads | 0.2ms
Proposition permission filter | Array filter per page | 0.1ms
Response assembly | JSON serialisation | 0.1ms
TOTAL typical | All operations combined | 13-33ms
TOTAL p99 (slow embedding) | Worst case local embedding | <100ms
Budget remaining under 200ms target | Headroom available | >100ms

