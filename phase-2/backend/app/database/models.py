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

CREATE_NOTION_OBJECTS_TABLE = """
CREATE TABLE IF NOT EXISTS notion_objects (
  notion_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  title TEXT NOT NULL,
  url TEXT NOT NULL,
  parent_id TEXT,
  last_edited_time TEXT NOT NULL,
  type TEXT NOT NULL,
  sync_status TEXT NOT NULL CHECK(sync_status IN ('discovered','synced','failed','empty','inaccessible')),
  error_message TEXT,
  last_synced_at TEXT,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
"""

CREATE_SOURCE_OBJECTS_TABLE = """
CREATE TABLE IF NOT EXISTS source_objects (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  connector_type TEXT NOT NULL,
  external_id TEXT NOT NULL,
  object_type TEXT NOT NULL,
  title TEXT NOT NULL,
  url TEXT,
  author TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  raw_json TEXT NOT NULL DEFAULT '{}',
  content_hash TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  FOREIGN KEY(tenant_id) REFERENCES tenants(id),
  UNIQUE(tenant_id, connector_type, external_id)
);
"""

CREATE_SOURCE_DOCUMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS source_documents (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  source_object_id TEXT NOT NULL,
  title TEXT NOT NULL,
  body_text TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id),
  FOREIGN KEY(source_object_id) REFERENCES source_objects(id)
);
"""

CREATE_SOURCE_SEGMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS source_segments (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  segment_type TEXT NOT NULL,
  heading_path TEXT,
  position INTEGER NOT NULL,
  text TEXT NOT NULL,
  author TEXT,
  timestamp TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id),
  FOREIGN KEY(document_id) REFERENCES source_documents(id)
);
"""

CREATE_SOURCE_RELATIONSHIPS_TABLE = """
CREATE TABLE IF NOT EXISTS source_relationships (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  from_object_id TEXT NOT NULL,
  to_object_id TEXT NOT NULL,
  relationship_type TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id),
  FOREIGN KEY(from_object_id) REFERENCES source_objects(id),
  FOREIGN KEY(to_object_id) REFERENCES source_objects(id)
);
"""

CREATE_KNOWLEDGE_PAGE_DRAFTS_TABLE = """
CREATE TABLE IF NOT EXISTS knowledge_page_drafts (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('DRAFT','PENDING','APPROVED','REJECTED')),
  validation_passed INTEGER NOT NULL DEFAULT 0,
  errors_json TEXT NOT NULL DEFAULT '[]',
  warnings_json TEXT NOT NULL DEFAULT '[]',
  validated_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
"""

CREATE_PROPOSITIONS_TABLE = """
CREATE TABLE IF NOT EXISTS propositions (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  draft_id TEXT NOT NULL,
  text TEXT NOT NULL,
  evidence_segment_ids_json TEXT NOT NULL,
  sensitivity TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(tenant_id) REFERENCES tenants(id),
  FOREIGN KEY(draft_id) REFERENCES knowledge_page_drafts(id)
);
"""

CREATE_SYNC_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS sync_runs (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  connector_type TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  counts_json TEXT NOT NULL DEFAULT '{}',
  error_message TEXT,
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
    cursor.execute(CREATE_NOTION_OBJECTS_TABLE)
    cursor.execute(CREATE_SOURCE_OBJECTS_TABLE)
    cursor.execute(CREATE_SOURCE_DOCUMENTS_TABLE)
    cursor.execute(CREATE_SOURCE_SEGMENTS_TABLE)
    cursor.execute(CREATE_SOURCE_RELATIONSHIPS_TABLE)
    cursor.execute(CREATE_KNOWLEDGE_PAGE_DRAFTS_TABLE)
    cursor.execute(CREATE_PROPOSITIONS_TABLE)
    cursor.execute(CREATE_SYNC_RUNS_TABLE)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_source_objects_external ON source_objects(tenant_id, connector_type, external_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_source_objects_hash ON source_objects(tenant_id, content_hash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_source_documents_object ON source_documents(tenant_id, source_object_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_source_segments_document_position ON source_segments(tenant_id, document_id, position)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_source_segments_hash ON source_segments(tenant_id, content_hash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_drafts_status ON knowledge_page_drafts(tenant_id, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_runs_started ON sync_runs(tenant_id, connector_type, started_at)")
    
    # Run dynamic migration to add current_stage column to ingestion_jobs if not exists
    try:
        cursor.execute("SELECT current_stage FROM ingestion_jobs LIMIT 1")
    except sqlite3.OperationalError:
        try:
            cursor.execute("ALTER TABLE ingestion_jobs ADD COLUMN current_stage TEXT DEFAULT 'queued'")
        except Exception as e:
            print(f"Migration error (current_stage): {e}")

    # Run dynamic migration to add failure_reason column to ingestion_jobs if not exists
    try:
        cursor.execute("SELECT failure_reason FROM ingestion_jobs LIMIT 1")
    except sqlite3.OperationalError:
        try:
            cursor.execute("ALTER TABLE ingestion_jobs ADD COLUMN failure_reason TEXT")
        except Exception as e:
            print(f"Migration error (failure_reason): {e}")
            
    # Add metadata_json to propositions (stores source_quotes, confidence without schema change)
    try:
        cursor.execute("SELECT metadata_json FROM propositions LIMIT 1")
    except sqlite3.OperationalError:
        try:
            cursor.execute("ALTER TABLE propositions ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
        except Exception as e:
            print(f"Migration error (propositions.metadata_json): {e}")

    conn.commit()
