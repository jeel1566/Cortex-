import sqlite3

CREATE_TENANTS_TABLE = """
CREATE TABLE IF NOT EXISTS tenants (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  git_repo_path TEXT NOT NULL,
  hnsw_index_path TEXT NOT NULL,
  config TEXT
);
"""

CREATE_AGENTS_TABLE = """
CREATE TABLE IF NOT EXISTS agents (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  name TEXT NOT NULL,
  authority_level INTEGER NOT NULL CHECK(authority_level BETWEEN 0 AND 5),
  scope TEXT NOT NULL,
  created_at TEXT NOT NULL,
  revoked_at TEXT,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
"""

CREATE_INGESTION_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS ingestion_jobs (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued','processing','complete','failed','awaiting_approval')),
  source_type TEXT NOT NULL CHECK(source_type IN ('slack','notion','github','document','agent_decision')),
  pages_created INTEGER DEFAULT 0,
  pages_updated INTEGER DEFAULT 0,
  conflicts_found INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
"""

CREATE_FEEDBACK_TABLE = """
CREATE TABLE IF NOT EXISTS feedback (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  query_id TEXT NOT NULL,
  feedback_type TEXT NOT NULL CHECK(feedback_type IN ('wrong_answer','missing_knowledge','outdated','conflict_missed')),
  affected_pages TEXT,
  correct_answer TEXT,
  reporter_subject TEXT,
  created_at TEXT NOT NULL,
  resynthesis_job_id TEXT,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id),
  FOREIGN KEY(resynthesis_job_id) REFERENCES ingestion_jobs(id)
);
"""

CREATE_QUERY_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS query_log (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  question TEXT NOT NULL,
  pages_read TEXT,
  total_latency_ms INTEGER NOT NULL,
  authority_level INTEGER NOT NULL,
  overall_confidence REAL,
  had_conflict BOOLEAN DEFAULT 0,
  had_knowledge_gap BOOLEAN DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
"""

def init_database(conn: sqlite3.Connection):
    """Initializes all SQLite database tables."""
    cursor = conn.cursor()
    cursor.execute(CREATE_TENANTS_TABLE)
    cursor.execute(CREATE_AGENTS_TABLE)
    cursor.execute(CREATE_INGESTION_JOBS_TABLE)
    cursor.execute(CREATE_FEEDBACK_TABLE)
    cursor.execute(CREATE_QUERY_LOG_TABLE)
    
    # Run dynamic migration to add current_stage column to ingestion_jobs if not exists
    try:
        cursor.execute("SELECT current_stage FROM ingestion_jobs LIMIT 1")
    except sqlite3.OperationalError:
        try:
            cursor.execute("ALTER TABLE ingestion_jobs ADD COLUMN current_stage TEXT DEFAULT 'queued'")
        except Exception as e:
            print(f"Migration error: {e}")
            
    conn.commit()
