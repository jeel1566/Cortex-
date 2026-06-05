Cortex
Founder's Guide — Plain Language  ·  v1.0  ·  May 2026

This document is written for you personally. Plain language. No jargon. Everything you need to build Cortex without getting lost.

# What are we actually building?
Think of Cortex like this: every company has knowledge scattered everywhere — Slack messages, Google docs, support tickets, people's heads. AI agents like Claude Code or Cursor cannot use that scattered knowledge reliably. They hallucinate policies, forget context, and get confused.
Cortex reads all of that scattered knowledge, organises it into structured pages (like a really smart book), and then any AI agent can ask it a question and get a complete, accurate answer in under a second.
That is it. That is the whole product.

# Phase 1 — The only question that matters (Days 1-5)
Before you write any more code, you must answer: does Cortex actually give better answers than just feeding documents to an AI? If the answer is no, you need to fix the architecture. If yes, you have a product.

## What to do on Day 1
Pick a real company. Could be your own project. Could be a friend's company. You need at least 6 months of Slack messages and a few policy documents.
Write 50 questions a new employee or AI agent might ask about that company. Real questions. Things like:
What is the process for approving a refund over $500?
Who do I contact if a customer's order never arrived?
What is our policy on remote work?
Why did we choose Stripe over PayPal?
Then find a human who works at that company and have them answer all 50 questions with sources. Save this as your ground truth file.
Then run the same 50 questions through basic RAG (LlamaIndex over the same documents). Score the RAG answers.
This tells you your starting point. You need to beat this score. If you do, you have something. If you do not, fix the ingestion pipeline before doing anything else.

## What to build in Days 2-5
Day 2: Build the embedding module (app/llm/embedding.py) — 2 hours. This is the piece that turns text into numbers so the system can find relevant pages fast.
Day 3: Replace the fake classifier and clusterer with real LLM calls — 3 hours. Right now the system cannot properly understand the structure of company knowledge.
Day 4: Add synthesis validation — 4 hours. This makes sure the AI does not hallucinate into your pages.
Day 5: Connect real Slack data. Run all 50 questions through Cortex. Score honestly. Compare to RAG.

# Phase 2 — Make it trustworthy (Days 6-10)
If Phase 1 shows Cortex beats RAG, you build the trust layer. This is what makes it safe to use in a real company.

## The six things to build in Phase 2
Git-based storage: convert page files to a Git repo. Every change becomes a commit. This gives you version history for free and makes the system auditable.
Authority levels: not every agent should read every page. L0 is public. L5 is owner. Build the JWT token system that enforces this.
Notion connector: many companies use Notion. Build the connector with 5-minute polling as the main sync method.
Feedback loop: when Claude Code gets a wrong answer, it needs a way to tell Cortex. Build POST /v1/feedback.
Tiered freshness: critical policy changes should update immediately. Minor changes can wait for daily review. Build the three-tier update system.
Approval inbox frontend: humans need a simple interface to approve or reject changes the system proposes.

# Phase 3 — Ship it (Days 11-15)
If Phase 2 works, you are ready to put it in front of a real customer.
Day 11-12: Build the GitHub connector. This makes Cortex work for developers using Claude Code or Cursor.
Day 13: Deploy to a single VM. Get webhook URLs working so Slack and GitHub can push updates automatically.
Day 14: Run the full 50-question benchmark on the deployed system. Publish the result honestly.
Day 15: Demo to first customer. Real data. Real questions. Real feedback.

# The six decisions you must make before writing code

# The prompts to use with your coding agent
## Prompt 1 — Starting Phase 1
We are building Cortex, a knowledge OS for AI agents. I need you to build the following TODAY:

1. Create app/llm/embedding.py
   - Use the fastembed library with BAAI/bge-small-en-v1.5 model
   - Expose a single function: encode(text: str) -> list[float]
   - Model must load once at startup, not per call
   - Target: under 30ms per encoding call
   - Write unit tests in tests/test_embedding.py

2. Wire embedding.py into the existing HNSW vector index
   - When a page is created or updated, generate its embedding and add to HNSW
   - When POST /v1/query is called, embed the question and search HNSW
   - Write integration test: create 5 pages, query, verify correct page returned

Existing codebase uses Python FastAPI, hnswlib, and DeepSeek-V3 via Azure AI Foundry.
Do not change any existing code unless necessary. Just add embedding.py and wire it in.

## Prompt 2 — Fixing the classifier stub
The file app/ingestion/classifier.py currently uses stub rule-based logic. I need you to replace it with real LLM-based classification.

The classifier must:
- Take a list of sentences as input
- Call DeepSeek-V3 (already configured in app/llm/deepseek.py) with a batch of sentences in one API call
- Return each sentence labelled as one of: CONDITION, PRESCRIPTION, PROCEDURE, EXCEPTION, OUTCOME
- Use this classification scheme:
  CONDITION: sets the context when something applies (if, when, for customers who)
  PRESCRIPTION: states what must or should happen (refunds must be, policy requires)
  PROCEDURE: describes how to do something (step 1, first, then)
  EXCEPTION: overrides the general rule (except for, unless, VIP customers)
  OUTCOME: describes what results (this means, therefore, the result is)

Do not change the function signature. Just replace the stub logic with the LLM call.
Write unit tests with at least 10 examples covering all 5 types.

## Prompt 3 — Building the Slack connector
I need you to build app/connectors/slack.py from scratch.

Requirements:
1. OAuth flow: accept a Slack Bot token and verify it has channels:history and channels:read scopes
2. Initial import: call conversations.list to get all channels, then conversations.history for each channel. Must handle rate limiting — Slack allows ~1 request/second. Use exponential backoff.
3. Each message must be normalised to this IngestionEvent format:
   { source: 'slack', event_type: 'created', object_type: 'message', object_id: '{channel}_{ts}', content: '{text}', author_id: '{user}', timestamp: '{ts as ISO 8601}', metadata: { channel: '{channel_name}', thread_id: '{thread_ts if reply}', authority_score: 0.5 } }
4. Filter before returning: skip messages under 20 words, skip bot messages, skip messages that are just emoji or links
5. Incremental sync: accept a since_timestamp parameter and only return messages after that timestamp
6. Write unit tests using mocked Slack API responses

The existing connector pattern is in app/connectors/github.py — follow the same structure.

## Prompt 4 — Building synthesis validation
I need you to add a validation pass to the ingestion pipeline.

After every LLM synthesis call (Pass 5 in app/ingestion/pipeline.py), run these three checks:

Check 1 — Proposition coverage:
- Extract factual claims from the source documents using a DeepSeek call
- Verify each source claim appears in the synthesised page
- Calculate coverage as (claims found in page) / (total source claims)
- If coverage < 0.90: re-run synthesis with explicit instruction to include missing claims
- Maximum 2 re-synthesis attempts

Check 2 — Hallucination detection:
- Extract every claim made in the synthesised page using a DeepSeek call
- For each page claim, verify it can be traced to at least one source document
- Calculate hallucination_rate as (unsourced claims) / (total page claims)
- If hallucination_rate > 0.02: strip unsourced claims and re-run validation

Check 3 — Completeness score:
- Ask DeepSeek: given only this synthesised page, can you answer the question that triggered this synthesis? Rate 1-10.
- If score < 7: re-synthesise with lower temperature (0.3) and more explicit constraints

Store results in the page YAML header under synthesis_validation: { proposition_coverage, hallucination_rate, completeness_score, validation_passed, validated_at }

Write unit tests for all three checks with both passing and failing examples.

## Prompt 5 — Building the feedback endpoint
I need you to implement POST /v1/feedback in app/api/routes/feedback.py.

Request schema:
{
  query_id: string (required),
  feedback_type: 'wrong_answer' | 'missing_knowledge' | 'outdated' | 'conflict_missed' (required),
  affected_pages: list[str] (optional — page IDs),
  correct_answer: string (optional — human provides correct answer)
}

What the endpoint must do:
1. Validate the JWT token — extract tenant_id and reporter subject
2. Look up the original query in query_log table using query_id — get the pages that were read
3. If affected_pages not provided, use the pages from the query log
4. For each affected page: set needs_review: true in the page YAML header and commit to Git
5. Store feedback record in the feedback SQLite table
6. Queue affected pages for re-synthesis (add to ingestion_jobs table with status: queued)
7. If correct_answer provided: store as seed alongside the re-synthesis job
8. Return: { feedback_id, status: 'received', pages_flagged, resynthesis_queued: true }

Write unit tests. Write integration test: submit feedback, verify page is flagged in YAML.

# Skills to learn to build this

# The most important things to remember
## Do not skip the evaluation set
Day 1 is the ground truth evaluation set. Do not write a single line of ingestion code until you have 50 verified questions and a RAG baseline score. This is how you prove the product works.

## Do not over-engineer
SQLite not PostgreSQL. No queue for now. Local VM not cloud. Simple synchronous code. The most common startup mistake is building v5 infrastructure for a v1 product. Add complexity only when something breaks.

## One thing at a time
Each phase has a clear goal. Phase 1: prove Cortex beats RAG. Phase 2: make it trustworthy. Phase 3: ship it. Do not mix phases. Finish Phase 1 before touching Phase 2.

## The product is only as good as the synthesis
Everything else — the graph, the traversal, the API — is scaffolding. The actual product is the quality of the synthesised pages. If the LLM writes bad pages, agents get bad answers. The synthesis validation pass in Phase 1 Day 4 is the most important piece of code you will write.

## Ship something real in 15 days
This plan gets you to a first customer demo in 15 working days. That is three weeks. If it is taking longer, something is wrong. Either the architecture is too complex, the scope crept, or you are perfecting things before they need to be perfect. Ship ugly, learn fast, fix what breaks.

### Table
Decision | Our answer | Why
Which embedding model? | fastembed + BAAI/bge-small-en-v1.5 | Local. Free. 10ms. No API calls. No vendor dependency.
Which LLM for synthesis? | DeepSeek-V3 via Azure AI Foundry | Already working in your codebase.
Which database for MVP? | SQLite | Zero setup. Works to 50,000 pages. Free.
Do we need a queue? | No — synchronous ingestion for MVP | Keep it simple. Add Celery + Redis when you have 5+ concurrent customers.
Do we need cloud hosting? | No — local or single VM for MVP | Do not spend money on infrastructure until you have a paying customer.
Which frontend auth? | Clerk | Fastest integration with Next.js. Free tier enough for MVP.



### Table
Skill | Why you need it | How to learn it | Time to useful
FastAPI | Your API framework — already in codebase | FastAPI docs tutorial at fastapi.tiangolo.com — do the full tutorial | 2 days
Git internals (gitpython) | Your page store is a Git repo — you need to commit programmatically | gitpython docs — read the cookbook section, try committing a file in Python | 1 day
JWT auth (PyJWT + Clerk) | Every API call uses JWT tokens — you need to create and verify them | JWT.io introduction, then Clerk Python SDK docs | 1 day
HNSW / hnswlib | Your vector search index — already wrapped in codebase | Read the hnswlib README on GitHub — 15 minutes, very clear | 15 minutes
fastembed | Your local embedding model | fastembed README on GitHub — 10 minutes to get running | 10 minutes
Slack Events API | Your most important connector | Read Slack Events API overview and Bot token scopes guide at api.slack.com | 2 hours
Webhooks in FastAPI | GitHub and Slack push events to your server — you receive them here | Build a simple webhook receiver with FastAPI — many tutorials available | 1 day
structlog | Structured logging for observability | structlog quickstart at structlog.org — 30 minutes | 30 minutes
pytest + pytest-asyncio | Testing FastAPI async endpoints — already in codebase | Real Python guide on testing FastAPI — 1 hour | 1 hour
Next.js 14 | Your frontend for Approval Inbox | Next.js official tutorial at nextjs.org/learn — do the full course | 2 days

