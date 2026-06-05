Cortex
Critique Response and Architecture v3.0  ·  v3.0  ·  May 2026

Source:  External AI critique plus hands-deep research findings
Verdict:  Every problem is real. Every solution is now locked into v3.0.
Key shift:  Stop marketing speed. Market reliability. 200ms of Truth, not 3.6ms of guesswork.

# Problem 1 — Human approval is an unscalable bottleneck
The problem: 10,000 docs requires 10-30 minutes of human review. 1,000,000 docs is impossible. Humans fall behind, knowledge goes stale, the living OS becomes a stale archive.

## The fix: Confidence-gated auto-approval
Not everything needs human review. Only uncertain things do. We implement a three-tier confidence gate on every synthesised page:


What this means in practice:
For a company with 10,000 docs: estimate 70% auto-approve, 25% standard queue, 5% blocked. Human reviews 250 pages not 10,000. Time: under 2 hours not 10-30.
For 1,000,000 docs: the math scales. Human reviews roughly 2,500 pages. Spread over initial onboarding this is manageable.
Pages in DRAFT state are not invisible. They can be queried by L4+ agents with a draft_included flag. The knowledge exists. It is just not trusted yet.

## Strict Mode synthesis — new rule
A page that fails synthesis validation MUST NOT be published. It stays in DRAFT or REJECTED state. This is non-negotiable. A wrong page confidently served is worse than no page at all.

page_states:
  DRAFT       # Synthesised but below confidence threshold — L4+ only
  PENDING     # Above threshold, queued for human review
  APPROVED    # Human approved or auto-approved — available to all permitted agents
  REJECTED    # Human rejected — never served — kept in Git for audit
  OUTDATED    # Newer version exists — served with outdated flag
  CONFLICTED  # Genuine error conflict unresolved — flagged on every response

## Audit trail as first-class citizen — new YAML field
Every page now stores its synthesis reasoning — which source segments created which propositions:
synthesis_audit:
  - proposition_id: prop_013_001
    text: "Refund window is 60 days"
    source_segments:
      - source: slack://C123/1705312800
        excerpt: "we moved to 60 day refunds last quarter"
        author: sarah.chen
        confidence: 0.97
  - proposition_id: prop_013_002
    text: "Refunds require original condition"
    source_segments:
      - source: notion://page/abc123
        excerpt: "items must be returned in original packaging"
        confidence: 0.91
This is not optional metadata. It is the core trust signal. Agents and humans can see exactly where every claim came from. The LLM reasoning is transparent.

# Problem 2 — NLI link detection can orphan knowledge
The problem: if NLI misses a link between a general policy and its exception, the BFS never finds the exception. Unlike RAG which might stumble on it via vector similarity, a broken graph link makes knowledge permanently invisible.

## The fix: Hybrid retrieval — graph plus vector fallback
Graph traversal is the primary path. Vector similarity is the safety net. They work together:


The vector safety net does two things: it catches knowledge the graph missed, and it tells you when your graph is broken. Every time the vector net finds something the graph did not, that is a signal to add a link.

## Graph health monitoring — new metric
Track: orphan_catch_rate — percentage of queries where vector net found relevant content the graph missed
Alert when: orphan_catch_rate exceeds 5% — this means your link detection is failing
Response: queue affected pages for re-link-detection and human review
Over time: orphan_catch_rate should trend toward zero as the graph fills in

# Problem 3 — Git is not a database at scale
The problem: frequent automated commits from Slack webhooks and GitHub pushes cause repository bloat. git diff and rollback become slow. Git lock files cause ingestion failures under concurrent load.

## The fix: Git for truth, SQLite for speed, clear migration path
Git and SQLite serve different purposes. We separate them clearly:


## Git commit rules — the new policy
Only APPROVED pages are committed to Git. DRAFT and REJECTED pages live in SQLite only.
One commit per page approval — not one commit per webhook event.
Batch commits: if 50 pages are approved in one human review session, that is one Git commit with 50 file changes.
Git garbage collection runs nightly — prune, repack, reduce loose objects.
Shallow clone for large tenants — agents read last 1000 commits only. Full history in cold storage.

## Scale migration path — clear and honest

# Problem 4 — Sensitivity classifier errors leak PII
The problem: a single misclassification by the sensitivity classifier could expose L4 admin data (salary, HR records) to an L0 public agent. This is a catastrophic security failure.

## The fix: conservative defaults plus double-check for personal claims
The sensitivity classifier must fail safe — when uncertain, classify UP not down:


## Double-check for high-stakes misclassification
Any proposition classified as Team (L1) or Public (L0) that came from a source with access_level confidential or department gets a mandatory second classification pass:
# Second pass check
if source.access_level in ['confidential', 'department'] and
   classified_sensitivity in ['public', 'team']:
    # Run second classification with more conservative prompt
    second_result = classify_sensitivity(proposition, mode='conservative')
    # Take the MORE restrictive result
    final_sensitivity = max(classified_sensitivity, second_result)
    # Flag for human review regardless
    flag_for_review = True

## Fallback: page-level restriction when claim classification fails
If the sensitivity classifier returns low confidence (below 0.85) on any proposition in a page, the entire page inherits the most restrictive source access_level. This is the old 'most restrictive wins' rule as a safety net.
When in doubt about a proposition's sensitivity: restrict it. A falsely restricted page is fixable. A leaked salary record is not.

# Problem 5 — Small embedding model sacrifices accuracy
The problem: bge-small-en-v1.5 at 384 dimensions is fast but may miss semantic nuance in complex domain-specific queries. We may sacrifice the accuracy that makes Cortex better than RAG.

## The fix: tiered embedding by query complexity
Not all queries need the same embedding quality. Simple factual queries work fine with small models. Complex multi-concept queries need better models. We detect complexity and route accordingly:


Default behaviour: always use bge-small local. Tenants with legal, medical, or technical knowledge bases can opt into the API-based model for complex queries in their config. They accept the higher latency. They get better accuracy on complex queries.
Both models are loaded at startup — no cold start latency
Complexity detection adds under 1ms — simple heuristic, not another LLM call
For MVP: start with bge-small only. Add bge-base when the eval set shows accuracy gaps.

# Problem 6 — Ground truth eval set creates sales friction
The problem: asking a prospective customer to write 50 questions and verified answers before trialling the product is too much friction. Most will say no. The sales cycle stalls before it starts.

## The fix: we build the eval set for them
The ground truth requirement was always for us, not for the customer. We prove Cortex works before we talk to customers. Here is the revised approach:


## The pre-built eval corpus
Before any customer contact we build an eval corpus using public company data — open source project documentation, public company handbooks, public legal policies. We run our 50-question benchmark on this. This proves Cortex beats RAG on real company knowledge without needing a specific customer's data.
When a customer asks 'does this actually work better than RAG?' we show them the benchmark on public data. Then we offer to run it on their data with their 10-question spot-check.

# Problem 7 — Business model and strategy gaps
## Missing connectors limit early market
The MVP excludes Notion and Zendesk — where most messy company data actually lives. Limiting MVP to Slack and GitHub restricts early customers to engineering-heavy teams.
Fix: Add Notion connector to Phase 1 not Phase 2. It is a polling connector — no webhook complexity. One day of work. Opens the product to every startup using Notion.

## Open source maintenance burden
Running OSS self-hosted tier and multi-tenant cloud simultaneously doubles engineering burden.
Fix: OSS tier is Git-export only. Customers get a CLI tool that exports their knowledge base as a portable Git repo they can host themselves. We do not maintain two server implementations. One server. One export format.

## Rate limit too low for multi-agent teams
100 queries per minute per tenant is too low when Claude Code, Cursor, and custom agents all query simultaneously.
Fix: 100 queries per minute per agent not per tenant. A tenant with 10 connected agents gets 1,000 queries per minute total. This is how cloud providers actually do it.

## JWT authority levels too rigid
Linear L0-L5 authority does not handle cross-functional permissions. An engineer needs L4 for code pages but L1 for HR pages.
Fix: Add scope qualifiers to tokens. authority_level sets the ceiling. scope qualifiers restrict the domain. Example: { authority_level: 4, domains: ['engineering', 'product'], exclude_domains: ['hr', 'finance'] }. L4 for engineering pages, effectively L0 for HR pages.

# Problem 8 — Marketing the wrong thing
## Stop marketing 3.6ms or even 200ms
Never lead with speed. Lead with reliability. The value proposition is not 'fast answers.' It is 'answers you can trust that cite exactly where they came from.' A hallucination in 3ms costs you a customer. A cited truth in 200ms builds trust.

The new positioning in one sentence:
Cortex gives your AI agents 200ms of Truth — complete, cited, auditable answers from your company's knowledge — not vector fragments and guesswork.


# The complete revised architecture — what changes

# The honest version of what Cortex is now
After all the critique, all the fixes, and all the honest rebuilding, here is what Cortex actually is:

Cortex is a knowledge OS that reads your company's scattered data, structures it into cited, validated, version-controlled knowledge pages, and serves them to any AI agent with a complete audit trail of every answer.

Every answer is traceable. Every claim has a source. Every wrong answer can be corrected and the correction is permanent. Every page that fails synthesis validation is blocked from publication.
It is not the fastest. It is not the cheapest to build. It is the only system that gives AI agents knowledge they can actually trust — and gives humans a way to verify that trust.
That is the product. That is what we are building. Everything else is implementation detail.

### Table
Confidence score | Synthesis validation | Action | Human needed?
≥0.95 and validation passed | Coverage ≥95%, hallucination 0%, completeness ≥9 | Auto-approve. Page goes live immediately. Logged for audit. | No
0.80-0.94 or validation passed with minor issues | Coverage 85-94%, hallucination <2%, completeness 7-8 | Queue for human review within 24 hours. Page is live as draft visible to L4+ only until approved. | Yes — but non-blocking
<0.80 or validation failed | Coverage <85%, hallucination ≥2%, or completeness <7 | Page stays in DRAFT state. Never published. Flagged in inbox as needs-attention. | Yes — blocking for this page only



### Table
Stage | Method | When used | What it catches
1. Entry page | HNSW vector similarity | Always | Finds the best starting point for any question
2. Primary traversal | Graph BFS — follow primary links | Always | Gets all guaranteed prerequisites
3. Secondary traversal | Graph BFS — conditional secondary links | When condition matches | Gets relevant exceptions and extensions
4. Vector safety net | HNSW search on remaining time budget | When time budget remains after graph traversal | Catches orphaned pages the graph missed — pages with high semantic similarity to the question that had no link path to the entry page
5. Orphan detection | Compare vector results to graph results | After every query | If vector finds a highly relevant page the graph never reached, flag it — the graph is missing a link



### Table
What | Where stored | Why
Page content and YAML header | Git repository — one commit per approved change only | Version control, audit trail, diff, rollback. But only for approved changes — not every draft.
Draft pages and pending synthesis | SQLite only — not committed to Git | Fast writes, easy cleanup, no Git bloat from rejected drafts
Ingestion job state | SQLite only | High-frequency updates, no audit needed
Query logs | SQLite only | Very high frequency, append-only, no Git needed
Feedback records | SQLite + one Git commit per resolved feedback | Audit trail matters for resolved feedback, not raw incoming
Synthesis audit log | Git — attached to page commit | Must be permanent and auditable



### Table
Stage | Pages | Storage | When to migrate
MVP | 0-50,000 | Git + SQLite as described | Now
Growth | 50,000-500,000 | Git + PostgreSQL replacing SQLite | When any tenant hits 50k pages
Scale | 500,000-5,000,000 | Git for audit trail only + PostgreSQL as primary + object storage for page content | When Git operations exceed 5 seconds
Enterprise | 5M+ | PostgreSQL primary + S3 for content + Git as cold audit archive | When Git becomes a bottleneck



### Table
Claim type | Default when uncertain | Reason
Personal claim (names, roles, salaries) | Confidential — L5 only | PII leak is catastrophic. False positive (over-restrict) is acceptable. False negative (under-restrict) is not.
Decision claim (who approved what) | Department — L3 | Decision context is often sensitive. Better to over-restrict.
Procedural claim (how to do something) | Team — L1 | Procedures are usually safe to share internally. Over-restriction is annoying but not catastrophic.
Factual claim (what the policy is) | Public or team — L0/L1 | Facts about company policy are usually safe. Err toward team not public when uncertain.



### Table
Query complexity | Detected by | Embedding model | Latency | When
Simple — single concept, short | Under 10 words OR single named entity | bge-small-en-v1.5 local 384 dims | 10ms | Default — 80% of queries
Standard — multiple concepts | 10-30 words OR multiple named entities | bge-base-en-v1.5 local 768 dims | 25ms | Standard queries — 15% of queries
Complex — domain-specific, long | Over 30 words OR legal/medical/technical terms detected | text-embedding-3-small via API (optional) | 80ms | Complex queries — 5% of queries. User opts in.



### Table
Old approach | New approach | Why
Ask customer to write 50 questions | We generate 50 questions from their data automatically using LLM | Customer does nothing. We do the work.
Ask customer to provide verified answers | We provide candidate answers, customer spot-checks 10 of 50 | 10 minutes of their time, not 2 hours
Run benchmark before demo | We demo first using questions WE know Cortex answers correctly | Show the working product first. Benchmark conversation happens after they are interested.
Block all sales until benchmark exists | Block only first demo on our own eval set — not customer's | Use our test company data to build our eval set. Never block a customer conversation.



### Table
Old marketing | New marketing | Why
Sub-200ms retrieval | 200ms of Truth | Speed is a commodity. Trust is the differentiator.
Better than RAG | Every answer cites its source | Customers do not care about RAG. They care about wrong answers costing them money.
Knowledge graph traversal | Your agents know your company | Technical architecture is not a benefit. Confident accurate agents are.
Conflict detection | Catches contradictions before your agents do | Frame as protection, not a feature.
Living knowledge OS | Never re-explain your company to an AI again | Emotional benefit, not feature description.



### Table
Component | Was | Now | Priority
Page states | approved or draft | DRAFT / PENDING / APPROVED / REJECTED / OUTDATED / CONFLICTED | P0 — build immediately
Synthesis validation | Optional check after synthesis | BLOCKING — page cannot publish if validation fails | P0 — non-negotiable
Synthesis audit log | Not existed | Stored with every page — maps every proposition to source segment | P0 — core trust signal
Confidence-gated approval | All pages go to human review | ≥0.95 auto-approve, 0.80-0.94 queue, <0.80 blocked | P0 — solves bottleneck
Git commit policy | Every synthesis is a commit | Only approved pages committed — DRAFT in SQLite only | P0 — prevents bloat
Retrieval | Graph only | Graph primary + HNSW vector safety net | P0 — prevents orphaned knowledge
Sensitivity classifier | Single pass | Single pass + mandatory double-check from sensitive sources | P0 — prevents PII leak
Embedding model | bge-small only | bge-small default + bge-base for complex queries | P1 — opt-in per tenant
Rate limiting | 100/min per tenant | 100/min per agent (not per tenant) | P1 — unblocks multi-agent teams
JWT scoping | Linear L0-L5 | L0-L5 ceiling + domain scope qualifiers | P1 — needed for enterprise
Eval set | Customer builds it | We build it from public data + customer spot-checks 10 questions | P0 — removes sales friction
Notion connector | Phase 2 | Phase 1 — polling, one day of work | P1 — opens market
OSS tier | Full server self-hosted | Git export CLI only — no second server to maintain | P2 — simplifies engineering
Marketing | Speed claims | Reliability and citation — 200ms of Truth | Now — immediately

