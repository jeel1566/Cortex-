Cortex
Application Flow Document  ·  v1.0  ·  May 2026

# 1. Flow 1 — Company First-Time Onboarding

# 2. Flow 2 — Ongoing Knowledge Updates

# 3. Flow 3 — Agent Query

# 4. Flow 4 — Developer Project (Claude Code / Cursor)

# 5. Flow 5 — Feedback and Re-synthesis

### Table
Step | Actor | What happens | System action | Human needed?
1 | Human | Signs up, creates company account via Clerk auth | Tenant record created, Git OS repo initialised, empty HNSW index created | Yes
2 | Human | Connects data source — clicks Connect Slack | OAuth flow opens, Cortex requests read-only Bot token, stores encrypted | Yes — OAuth approval
3 | System | Pulls historical Slack data | API calls with rate-limit backoff queue, all messages normalised to IngestionEvents | No
4 | System | Filter pass | Removes duplicates, short messages, calendar invites — 60-70% data eliminated | No
5 | System | PII pass | Presidio + regex detects and redacts names, emails, phones, SSNs before LLM sees anything | No
6 | System | Classify pass | DeepSeek labels every sentence as CONDITION / PRESCRIPTION / PROCEDURE / EXCEPTION / OUTCOME | No
7 | System | Cluster pass | Groups sentences into decision units — one unit per answerable question | No
8 | System | Synthesise pass | LLM writes one canonical page per cluster. Sources cited in each proposition. | No
9 | System | Validate pass | Checks proposition coverage >90%, hallucination <2%, completeness >7/10. Re-synthesises failures. | No
10 | System | Conflict detection | Finds contradictions across pages. Classifies as temporal / contextual / specificity / error. | No
11 | System | Build indexes | Generates fastembed embeddings for all pages. Loads HNSW. Builds graph adjacency lists. | No
12 | Human | Review approval inbox | Sees all synthesised pages, flagged conflicts, low-confidence pages. One-click approve or reject. | Yes — 10-30 min
13 | System | OS goes live | All approved pages published. HNSW and graph updated. API accepts queries. | No
14 | Agent | First query | Agent calls POST /v1/query. Gets pages + traversal path in under 200ms. | No



### Table
Trigger | Urgency tier | What happens | Human approval?
Admin explicitly changes a policy | Immediate | Re-synthesis queued now. Push notification to approver. Must approve within 1 hour or auto-reverts. | Yes — within 1 hour
Source document updated by high-authority author | Standard | Re-synthesis queued. Appears in approval inbox within 15 minutes. | Yes — within 24 hours
Minor edit — meaning unchanged, hash matches | Ignored | Content hash compared. Match found. Nothing happens. Zero cost. | No
Low-authority source change (old Slack edit) | Background | Flagged for review in weekly batch. Not queued for synthesis. | Yes — weekly batch
Agent feedback — wrong_answer | Standard | Page flagged needs_review. Re-synthesis queued with feedback as seed. | Yes — after re-synthesis



### Table
Step | What happens | Latency
1. Agent sends question | POST /v1/query with question and Bearer JWT token | 0ms
2. Auth check | JWT decoded, signature verified, expiry checked, tenant ID and authority level extracted | 1ms
3. Embed question | fastembed encodes question to 384-dim vector using local BAAI/bge-small model | 10-30ms
4. HNSW lookup | Top-3 most similar pages found in in-memory HNSW index for this tenant | 3ms
5. Permission filter | Each candidate page checked against agent's authority level and scope. Remove inaccessible pages. | 0.1ms
6. Phase 1 traversal — primary links | BFS exhausts all primary links from entry page. Visited set tracks all read pages. | 0.3ms
7. Phase 2 traversal — secondary links | Priority queue built from secondary links sorted by relevance score. Consume within remaining time budget. | 0.3ms
8. Proposition filter | For each page, filter out propositions above agent's authority level. L1 agent never sees confidential props. | 0.1ms
9. Conflict assembly | Collect conflict flags from all read pages. Include in response. | 0.05ms
10. Response assembly | Build JSON response: pages, traversal_path, conflicts, confidence, latency_ms | 0.1ms
11. Return | 200 OK with full response. Total: 13-33ms typical. Under 200ms p99. | Done



### Table
Step | Actor | What happens
1 | Developer | Runs: cortex init in project root. Enters API key.
2 | Cortex CLI | Reads README, existing docs, full git history. Calls POST /v1/ingest for initial load.
3 | System | Ingestion pipeline runs. Commits become behavioral trace pages. PRs become decision pages. ADRs become policy pages.
4 | Developer | Makes code changes. Commits to git.
5 | GitHub webhook | Cortex receives push event. Ingests commit diff and PR description.
6 | System | Affected pages re-synthesised. HNSW and graph updated. Conflict detection runs.
7 | Claude Code | Asks: why was the auth module changed last week?
8 | Cortex API | Returns page built from the PR that changed the auth module — with PR description, review comments, decision rationale.
9 | Claude Code | Makes an architectural decision. Calls POST /v1/ingest with the decision as source_type: agent_decision.
10 | System | Decision synthesised into a page. Validation runs. Goes to approval inbox.
11 | Developer | Reviews and approves the decision page in approval inbox.
12 | Future agents | Any agent querying about this area gets the decision context permanently.



### Table
Step | What happens
1. Agent gets wrong answer | Query returns page with incorrect or outdated information.
2. Agent flags it | Calls POST /v1/feedback with query_id, feedback_type: wrong_answer, optionally correct_answer.
3. System records feedback | Stored in Git OS repo as commit. Page flagged needs_review: true in YAML header.
4. Re-synthesis queued | Page added to re-synthesis queue with original sources plus feedback as additional seed.
5. Re-synthesis runs | LLM re-synthesises the page. Validation pass runs automatically.
6. If validation passes | New page version goes to approval inbox.
7. Human approves | Page published as new version. Git commit records the correction with approver.
8. Future queries | Next agent asking the same question gets the corrected page.
9. Feedback metric updated | Prometheus counter for this page's feedback rate updated. High feedback rate triggers review alert.

