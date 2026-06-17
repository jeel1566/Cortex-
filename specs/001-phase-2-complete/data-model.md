# Data Model: Phase 2 — Make it Complete

This document details the database schema, entity structures, and constraints for the SQLite database.

---

## SQLite Database Schemas

### 1. Tenants
Represents a corporate customer tenant.
```sql
CREATE TABLE tenants (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  git_repo_path TEXT NOT NULL,
  hnsw_index_path TEXT NOT NULL,
  config JSON
);
```

### 2. Agents
Users or automated agents authorized to query or interact with a tenant store.
```sql
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
```

### 3. Ingestion Jobs
Tracks the state of bulk or incremental ingestion jobs.
```sql
CREATE TABLE ingestion_jobs (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  status TEXT NOT NULL CHECK(status IN ('queued','processing','complete','failed','awaiting_approval')),
  source_type TEXT NOT NULL CHECK(source_type IN ('slack','notion','github','document','agent_decision')),
  pages_created INTEGER DEFAULT 0,
  pages_updated INTEGER DEFAULT 0,
  conflicts_found INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  completed_at TEXT
);
```

### 4. Feedback
Stores user-submitted flags or corrections on queries or page content.
```sql
CREATE TABLE feedback (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  query_id TEXT NOT NULL,
  feedback_type TEXT NOT NULL CHECK(feedback_type IN ('wrong_answer','missing_knowledge','outdated','conflict_missed')),
  affected_pages JSON,
  correct_answer TEXT,
  reporter_subject TEXT,
  created_at TEXT NOT NULL,
  resynthesis_job_id TEXT REFERENCES ingestion_jobs(id)
);
```

### 5. Query Log
Logs all incoming query operations, latencies, and knowledge quality metrics.
```sql
CREATE TABLE query_log (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  question TEXT NOT NULL,
  pages_read JSON,
  total_latency_ms INTEGER NOT NULL,
  authority_level INTEGER NOT NULL,
  overall_confidence REAL,
  had_conflict BOOLEAN DEFAULT 0,
  had_knowledge_gap BOOLEAN DEFAULT 0,
  created_at TEXT NOT NULL
);
```
