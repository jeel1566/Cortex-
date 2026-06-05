Cortex
Backend Schema, API, and Database  ·  v1.0  ·  May 2026

# 1. Page YAML Schema
Every knowledge page is a markdown file with this YAML frontmatter header:
---
id: page_013
title: Standard Refund Policy
version: 3
content_hash: sha256:a1b2c3d4...
owner: finance_team
last_updated: 2026-01-15T09:00:00Z
access_level: team  # public | team | department:X | confidential
primary_links:
  - page_042  # always read with this page
secondary_links:
  - condition: "damaged OR defect OR broken"
    page: page_055
  - condition: "late OR delayed OR not arrived"
    page: page_061
conflicts:
  - type: temporal
    conflicting_page: page_022
    description: page_022 says 30 days, we say 60 days
needs_review: false
feedback_count: 0
synthesis_validation:
  proposition_coverage: 0.94
  hallucination_rate: 0.00
  completeness_score: 8.5
  validation_passed: true
  validated_at: 2026-01-15T09:00:00Z
change_history:
  - version: 3
    date: 2026-01-15
    changed: window 30 days to 60 days
    reason: Q1 policy update
    approved_by: sarah.chen
  - version: 2
    date: 2025-11-20
    changed: added VIP exception link
    reason: new enterprise tier launch
sources:
  - slack://C123ABC/1705312800
  - notion://page/abc123def
---

# 2. SQLite Database Schema
## tenants table
CREATE TABLE tenants (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  git_repo_path TEXT NOT NULL,
  hnsw_index_path TEXT NOT NULL,
  config JSON
);

## agents table
CREATE TABLE agents (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  name TEXT NOT NULL,
  authority_level INTEGER NOT NULL CHECK(authority_level BETWEEN 0 AND 5),
  scope JSON NOT NULL,
  created_at TEXT NOT NULL,
  revoked_at TEXT,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);

## ingestion_jobs table
CREATE TABLE ingestion_jobs (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued','processing','complete','failed','awaiting_approval')),
  source_type TEXT NOT NULL,
  pages_created INTEGER DEFAULT 0,
  pages_updated INTEGER DEFAULT 0,
  conflicts_found INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  completed_at TEXT
);

## feedback table
CREATE TABLE feedback (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  query_id TEXT NOT NULL,
  feedback_type TEXT NOT NULL,
  affected_pages JSON,
  correct_answer TEXT,
  reporter_subject TEXT,
  created_at TEXT NOT NULL,
  resynthesis_job_id TEXT
);

## query_log table
CREATE TABLE query_log (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  question TEXT NOT NULL,
  pages_read JSON,
  total_latency_ms INTEGER,
  authority_level INTEGER,
  overall_confidence REAL,
  had_conflict BOOLEAN,
  had_knowledge_gap BOOLEAN,
  created_at TEXT NOT NULL
);

# 3. Complete API Specification
## Base URL and versioning
Base URL: http://localhost:8000 (MVP) or https://api.cortex.ai (production)
Version: /v1/ prefix on all endpoints
Content-Type: application/json
Auth: Authorization: Bearer {JWT}

## POST /v1/query

Response 200:
{
  query_id: string,
  pages: [{ id, title, version, content, propositions, last_updated, owner, access_level, conflicts, synthesis_validation, confidence }],
  traversal_path: [{ from, to, link_type, condition_matched, latency_ms }],
  knowledge_gaps: string[],
  overall_confidence: float (0-1),
  total_latency_ms: integer,
  pages_read: integer,
  token_estimate: integer
}


## GET /v1/page/:id
Response 200:
{
  id, title, version, content, propositions: [{ id, text, sensitivity }],
  last_updated, owner, access_level,
  primary_links: [{ id, title }],
  secondary_links: [{ condition, page: { id, title } }],
  conflicts: [{ type, conflicting_page, description }],
  synthesis_validation: { proposition_coverage, hallucination_rate, completeness_score },
  change_history: [{ version, date, changed, reason, approved_by }],
  sources: string[],
  needs_review: boolean,
  feedback_count: integer
}

## POST /v1/ingest
Request:
{
  source_type: 'slack' | 'notion' | 'github' | 'document' | 'agent_decision',
  content: string,
  metadata: { author, timestamp, source_url?, authority_level, urgency: 'immediate'|'standard'|'background' }
}

Response 202:
{ job_id, status: 'queued', estimated_completion_ms, poll_url }

## GET /v1/ingest/:job_id
Response 200:
{
  job_id, status: 'complete'|'processing'|'failed'|'awaiting_approval',
  pages_created, pages_updated, conflicts_found,
  pages_awaiting_approval: string[],
  completed_at?
}

## POST /v1/feedback
Request:
{
  query_id: string,
  feedback_type: 'wrong_answer'|'missing_knowledge'|'outdated'|'conflict_missed',
  affected_pages?: string[],
  correct_answer?: string
}

Response 200:
{ feedback_id, status: 'received', pages_flagged, resynthesis_queued: boolean }

## Rate limits and headers

# 4. MCP Server Specification
## Tool: query_knowledge
{
  name: 'query_knowledge',
  description: 'Ask a natural language question about this company and get back structured knowledge pages with full context. Use this when you need to understand a company policy, process, decision, or how something works. Returns pages, traversal path, and confidence score.',
  inputSchema: {
    type: 'object',
    properties: {
      question: { type: 'string', description: 'Natural language question. Be specific.', maxLength: 2000 },
      time_budget_ms: { type: 'integer', default: 150, minimum: 50, maximum: 500 }
    },
    required: ['question']
  }
}

## Tool: get_page
{
  name: 'get_page',
  description: 'Retrieve a specific knowledge page by ID. Use this when query_knowledge returns a page ID and you need the full content with change history and sources.',
  inputSchema: {
    type: 'object',
    properties: { page_id: { type: 'string', description: 'Page ID from query_knowledge response' } },
    required: ['page_id']
  }
}

## Tool: ingest_data
{
  name: 'ingest_data',
  description: 'Add new knowledge to the system. Use this when you make a decision that should be remembered, or when you have new information that updates existing knowledge. Requires L2+ authority.',
  inputSchema: {
    type: 'object',
    properties: {
      content: { type: 'string', description: 'The knowledge to ingest' },
      source_type: { type: 'string', enum: ['agent_decision', 'document'] },
      urgency: { type: 'string', enum: ['immediate', 'standard', 'background'], default: 'standard' }
    },
    required: ['content', 'source_type']
  }
}

### Table
Field | Type | Required | Default | Validation
question | string | Yes | — | 1-2000 characters
time_budget_ms | integer | No | 150 | 50-500
max_pages | integer | No | 10 | 1-20
include_traversal_path | boolean | No | true | —
include_conflicts | boolean | No | true | —



### Table
Status | Error code | Trigger
400 | INVALID_QUESTION | Empty or over 2000 chars
401 | UNAUTHORIZED | Missing or invalid JWT
403 | INSUFFICIENT_AUTHORITY | Token level too low
404 | NO_KNOWLEDGE | No pages ingested yet
429 | RATE_LIMITED | Over 100 queries/min — X-RateLimit-Remaining header included
500 | TRAVERSAL_ERROR | Internal error — includes query_id for debugging
503 | INDEX_LOADING | HNSW being rebuilt — retry_after_ms included



### Table
Header | Value | Meaning
X-RateLimit-Limit | 100 | Max queries per minute
X-RateLimit-Remaining | 87 | Queries remaining this minute
X-RateLimit-Reset | 1748001234 | Unix timestamp when limit resets
X-Request-Id | req_abc123 | Unique request ID for debugging
X-Latency-Ms | 28 | Total server-side latency in ms

