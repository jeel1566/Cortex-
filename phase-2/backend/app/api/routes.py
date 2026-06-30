import os
import uuid
import datetime
import json
import time
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from app.api.auth import get_current_agent, PermissionChecker
from app.database.connection import get_tenant_connection
from app.query_engine import CortexQueryEngine, _load_page
from app.ingestion.pipeline import run_ingestion_pipeline
from app.config import TENANTS_DIR
from app.logging import get_logger
from prometheus_client import Counter, Histogram

logger = get_logger(__name__)
router = APIRouter()

from prometheus_client import REGISTRY
if "cortex_queries_total" in REGISTRY._names_to_collectors:
    QUERIES_COUNTER = REGISTRY._names_to_collectors["cortex_queries_total"]
else:
    QUERIES_COUNTER = Counter("cortex_queries_total", "Total queries executed", ["tenant_id"])

if "cortex_query_latency_seconds" in REGISTRY._names_to_collectors:
    LATENCY_HISTOGRAM = REGISTRY._names_to_collectors["cortex_query_latency_seconds"]
else:
    LATENCY_HISTOGRAM = Histogram("cortex_query_latency_seconds", "Query latency distribution", ["tenant_id"])

# ── Pydantic Request Models ──────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., max_length=2000)
    time_budget_ms: Optional[int] = 150

class IngestRequest(BaseModel):
    source_type: str
    content: str
    metadata: Dict[str, Any] = {}

class FeedbackRequest(BaseModel):
    query_id: str
    feedback_type: str
    affected_pages: Optional[List[str]] = []
    correct_answer: Optional[str] = ""

# ── POST /v1/query ───────────────────────────────────────────────────────────

@router.post("/query")
def query_knowledge(
    request: QueryRequest,
    agent: dict = Depends(PermissionChecker(min_level=0))
):
    tenant_id = agent["tenant_id"]
    clearance_num = agent.get("authority_level", 1)
    clearance_map = {0: "public", 1: "team", 2: "confidential", 3: "restricted"}
    clearance_str = clearance_map.get(clearance_num, "team")
    
    user = {
        "clearance_level": clearance_str,
        "department": agent.get("department"),
        "role": agent.get("role", "member")
    }
    question = request.question
    
    tenant_dir = os.path.join(TENANTS_DIR, tenant_id)
    if not os.path.exists(tenant_dir):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant repository has not been initialized. No pages exist."
        )
        
    try:
        t0 = time.time()
        from app.retrieval.hybrid_query import HybridQueryEngine
        engine = HybridQueryEngine(tenant_id=tenant_id)
        result = engine.query(question, user=user)
        latency_sec = time.time() - t0
        QUERIES_COUNTER.labels(tenant_id=tenant_id).inc()
        LATENCY_HISTOGRAM.labels(tenant_id=tenant_id).observe(latency_sec)
    except Exception as e:
        logger.error("query_error", tenant_id=tenant_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error running query: {e}"
        )
        
    conn = get_tenant_connection(tenant_id)
    cursor = conn.cursor()
    query_id = f"q_{uuid.uuid4().hex[:8]}"
    
    try:
        cursor.execute(
            """
            INSERT INTO query_log (
                id, tenant_id, question, pages_read, total_latency_ms,
                authority_level, overall_confidence, had_conflict, had_knowledge_gap, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query_id,
                tenant_id,
                question,
                json.dumps(result["pages_read"]),
                result["latency_ms"],
                clearance_num,
                result["confidence"],
                0,
                1 if len(result["knowledge_gaps"]) > 0 else 0,
                datetime.datetime.utcnow().isoformat() + "Z"
            )
        )
        conn.commit()
    except Exception as e:
        logger.error("query_log_error", error=str(e))
        
    return {
        "answer": result["answer"],
        "citations": result["citations"],
        "pages_read": result["pages_read"],
        "source_segments_read": result["source_segments_read"],
        "redactions": result["redactions"],
        "knowledge_gaps": result["knowledge_gaps"],
        "confidence": result["confidence"],
        "latency_ms": result["latency_ms"],
        "query_id": query_id,
        "pages": [
            {
                "id": pid,
                "title": f"Page {pid}",
                "content": f"Context block retrieved for {pid}"
            } for pid in result["pages_read"]
        ]
    }

# ── GET /v1/pages ────────────────────────────────────────────────────────────

@router.get("/pages")
def list_pages(
    agent: dict = Depends(PermissionChecker(min_level=0))
):
    tenant_id = agent["tenant_id"]
    tenant_dir = os.path.join(TENANTS_DIR, tenant_id)
    pages_dir = os.path.join(tenant_dir, "repo")
    
    if not os.path.exists(pages_dir):
        return []
        
    pages = []
    try:
        for filename in os.listdir(pages_dir):
            if filename.endswith(".md"):
                page_id = filename[:-3]
                res = _load_page(pages_dir, page_id)
                if res:
                    metadata, _ = res
                    pages.append({
                        "id": page_id,
                        "title": metadata.get("title", f"Page {page_id}"),
                        "version": metadata.get("version", 1),
                        "owner": metadata.get("owner", "team"),
                        "access_level": metadata.get("access_level", "team"),
                        "last_updated": metadata.get("last_updated"),
                    })
    except Exception as e:
        logger.error("list_pages_error", tenant_id=tenant_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error listing pages: {e}"
        )
    return pages

# ── GET /v1/page/{page_id} ───────────────────────────────────────────────────

@router.get("/page/{page_id}")
def get_page(
    page_id: str,
    agent: dict = Depends(PermissionChecker(min_level=0))
):
    tenant_id = agent["tenant_id"]
    clearance = agent["authority_level"]
    
    tenant_dir = os.path.join(TENANTS_DIR, tenant_id)
    pages_dir = os.path.join(tenant_dir, "repo")
    
    res = _load_page(pages_dir, page_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found."
        )
        
    metadata, body = res
    
    # Filter propositions based on user clearance level
    propositions = metadata.get("propositions", [])
    filtered_props = []
    
    for prop in propositions:
        sens = prop.get("sensitivity", "team")
        required_level = 0
        if sens == "team":
            required_level = 1
        elif sens == "confidential":
            required_level = 3
            
        if clearance >= required_level:
            filtered_props.append(prop)
        else:
            filtered_props.append({
                "id": prop.get("id"),
                "text": "[REDACTED - INSUFFICIENT CLEARANCE]",
                "sensitivity": sens
            })
            
    return {
        "id": page_id,
        "title": metadata.get("title", f"Page {page_id}"),
        "version": metadata.get("version", 1),
        "content": body,
        "propositions": filtered_props,
        "last_updated": metadata.get("last_updated"),
        "owner": metadata.get("owner", "team"),
        "access_level": metadata.get("access_level", "team"),
        "sources": metadata.get("sources", [])
    }

# ── Background Ingestion Task ────────────────────────────────────────────────

def run_background_ingest(tenant_id: str, job_id: str, content: str, source_type: str):
    conn = get_tenant_connection(tenant_id)
    cursor = conn.cursor()
    
    try:
        # Update status to processing
        cursor.execute(
            "UPDATE ingestion_jobs SET status = 'processing' WHERE id = ?",
            (job_id,)
        )
        conn.commit()
        
        # Raw content parsing (support single message or line-separated text)
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        messages = []
        for i, line in enumerate(lines):
            messages.append({
                "text": line,
                "user": f"user_{i}",
                "channel": "general",
                "timestamp": f"{time.time() + i}",
                "source_id": f"{source_type}://general/{time.time() + i}"
            })
            
        # Run compiler pipeline
        pages_created = run_ingestion_pipeline(tenant_id, messages, job_id=job_id)
        
        # Mark job complete
        cursor.execute(
            """
            UPDATE ingestion_jobs 
            SET status = 'complete', pages_created = ?, completed_at = ?
            WHERE id = ?
            """,
            (
                len(pages_created),
                datetime.datetime.utcnow().isoformat() + "Z",
                job_id
            )
        )
        conn.commit()
    except Exception as e:
        logger.error("background_ingest_failed", job_id=job_id, error=str(e))
        cursor.execute(
            "UPDATE ingestion_jobs SET status = 'failed', completed_at = ? WHERE id = ?",
            (datetime.datetime.utcnow().isoformat() + "Z", job_id)
        )
        conn.commit()

# ── POST /v1/ingest ──────────────────────────────────────────────────────────

@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
def ingest_data(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    agent: dict = Depends(PermissionChecker(min_level=2))
):
    tenant_id = agent["tenant_id"]
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    
    conn = get_tenant_connection(tenant_id)
    cursor = conn.cursor()
    
    # Log job entry
    cursor.execute(
        """
        INSERT INTO ingestion_jobs (
            id, tenant_id, status, source_type, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            job_id,
            tenant_id,
            "queued",
            request.source_type,
            datetime.datetime.utcnow().isoformat() + "Z"
        )
    )
    conn.commit()
    
    # Dispatch asynchronous background task
    background_tasks.add_task(
        run_background_ingest,
        tenant_id=tenant_id,
        job_id=job_id,
        content=request.content,
        source_type=request.source_type
    )
    
    return {
        "job_id": job_id,
        "status": "queued",
        "poll_url": f"/v1/ingest/{job_id}"
    }

# ── GET /v1/ingest/{job_id} ──────────────────────────────────────────────────

@router.get("/ingest/{job_id}")
def get_ingest_status(
    job_id: str,
    agent: dict = Depends(PermissionChecker(min_level=2))
):
    tenant_id = agent["tenant_id"]
    conn = get_tenant_connection(tenant_id)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingestion job {job_id} not found."
        )
        
    return {
        "job_id": row["id"],
        "status": row["status"],
        "current_stage": row["current_stage"] if "current_stage" in row.keys() else "queued",
        "pages_created": row["pages_created"],
        "pages_updated": row["pages_updated"],
        "conflicts_found": row["conflicts_found"],
        "completed_at": row["completed_at"],
        "failure_reason": row["failure_reason"] if "failure_reason" in row.keys() else None
    }

# ── GET /v1/ingest/latest ──────────────────────────────────────────────────

@router.get("/ingest/latest")
def get_latest_ingest_status(
    agent: dict = Depends(PermissionChecker(min_level=1))
):
    tenant_id = agent["tenant_id"]
    conn = get_tenant_connection(tenant_id)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM ingestion_jobs WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 1",
        (tenant_id,)
    )
    row = cursor.fetchone()
    
    if not row:
        return {"job_id": None, "status": "none"}
        
    return {
        "job_id": row["id"],
        "status": row["status"],
        "current_stage": row["current_stage"] if "current_stage" in row.keys() else "queued",
        "pages_created": row["pages_created"],
        "pages_updated": row["pages_updated"],
        "conflicts_found": row["conflicts_found"],
        "completed_at": row["completed_at"]
    }

# ── POST /v1/feedback ────────────────────────────────────────────────────────


@router.post("/feedback")
def submit_feedback(
    request: FeedbackRequest,
    background_tasks: BackgroundTasks,
    agent: dict = Depends(PermissionChecker(min_level=1))
):
    tenant_id = agent["tenant_id"]
    feedback_id = f"fb_{uuid.uuid4().hex[:8]}"
    
    conn = get_tenant_connection(tenant_id)
    cursor = conn.cursor()
    
    # Insert feedback entry
    cursor.execute(
        """
        INSERT INTO feedback (
            id, tenant_id, query_id, feedback_type, affected_pages, correct_answer, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            feedback_id,
            tenant_id,
            request.query_id,
            request.feedback_type,
            json.dumps(request.affected_pages),
            request.correct_answer,
            datetime.datetime.utcnow().isoformat() + "Z"
        )
    )
    conn.commit()
    
    # Trigger re-synthesis task if correct answer correction is provided
    resynthesis_queued = False
    if request.correct_answer and request.affected_pages:
        resynthesis_queued = True
        job_id = f"job_re_{uuid.uuid4().hex[:8]}"
        
        cursor.execute(
            """
            INSERT INTO ingestion_jobs (
                id, tenant_id, status, source_type, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                job_id,
                tenant_id,
                "queued",
                "agent_decision",
                datetime.datetime.utcnow().isoformat() + "Z"
            )
        )
        # Update feedback link to job
        cursor.execute("UPDATE feedback SET resynthesis_job_id = ? WHERE id = ?", (job_id, feedback_id))
        conn.commit()
        
        # Dispatch background re-synthesis job
        background_tasks.add_task(
            run_background_ingest,
            tenant_id=tenant_id,
            job_id=job_id,
            content=f"Correction feedback for {', '.join(request.affected_pages)}: {request.correct_answer}",
            source_type="agent_decision"
        )
        
    return {
        "feedback_id": feedback_id,
        "status": "received",
        "pages_flagged": request.affected_pages,
        "resynthesis_queued": resynthesis_queued
    }

# ── GET /v1/notion/status ────────────────────────────────────────────────────

@router.get("/notion/status")
def get_notion_status(
    agent: dict = Depends(PermissionChecker(min_level=0))
):
    """
    Returns counts and statuses of discovered, synced, failed, empty,
    and inaccessible Notion objects for the tenant.
    """
    tenant_id = agent["tenant_id"]
    conn = get_tenant_connection(tenant_id)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT sync_status, COUNT(*) as count 
        FROM notion_objects 
        WHERE tenant_id = ? 
        GROUP BY sync_status
        """,
        (tenant_id,)
    )
    rows = cursor.fetchall()
    
    stats = {
        "discovered": 0,
        "synced": 0,
        "failed": 0,
        "empty": 0,
        "inaccessible": 0
    }
    for row in rows:
        status_key = row["sync_status"]
        if status_key in stats:
            stats[status_key] = row["count"]

    cursor.execute(
        """
        SELECT notion_id, title, url, type, sync_status, error_message, last_synced_at 
        FROM notion_objects 
        WHERE tenant_id = ?
        ORDER BY last_synced_at DESC, title ASC
        """,
        (tenant_id,)
    )
    objects = []
    for row in cursor.fetchall():
        objects.append({
            "notion_id": row["notion_id"],
            "title": row["title"],
            "url": row["url"],
            "type": row["type"],
            "sync_status": row["sync_status"],
            "error_message": row["error_message"],
            "last_synced_at": row["last_synced_at"]
        })

    cursor.execute("SELECT config FROM tenants WHERE id = ?", (tenant_id,))
    row = cursor.fetchone()
    tenant_config = json.loads(row["config"]) if row and row["config"] else {}
    notion_cfg = tenant_config.get("notion", {})
    
    return {
        "enabled": notion_cfg.get("enabled", False),
        "database_id": notion_cfg.get("database_id", ""),
        "last_polled": notion_cfg.get("last_polled", ""),
        "summary": stats,
        "objects": objects
    }

# ── GET and POST /v1/settings ───────────────────────────────────────────────

class SettingsRequest(BaseModel):
    ai_provider: str
    config: Dict[str, Any]
    connectors: Optional[Dict[str, Any]] = None

@router.get("/settings")
def get_settings(
    agent: dict = Depends(PermissionChecker(min_level=0))
):
    tenant_id = agent["tenant_id"]
    conn = get_tenant_connection(tenant_id)
    cursor = conn.cursor()
    cursor.execute("SELECT config FROM tenants WHERE id = ?", (tenant_id,))
    row = cursor.fetchone()
    
    default_ai_config = {
        "ollama_endpoint": "http://localhost:11434/v1",
        "ollama_model": "llama3",
        "web_api_endpoint": "",
        "web_api_key": "",
        "web_api_model": "llama-3.1-8b-instant",
        "codex_endpoint": "ws://127.0.0.1:4500",
        "codex_model": ""
    }
    default_notion_config = {
        "enabled": False,
        "database_id": "",
        "api_key": "",
        "last_polled": ""
    }
    default_slack_config = {
        "enabled": False,
        "token": "",
        "channel": ""
    }
    
    if not row or not row["config"]:
        return {
            "ai_provider": "not_configured",
            "config": default_ai_config,
            "connectors": {
                "notion": default_notion_config,
                "slack": default_slack_config
            }
        }
    
    try:
        tenant_config = json.loads(row["config"])
    except Exception:
        tenant_config = {}
        
    ai_provider = tenant_config.get("ai_provider", "not_configured")
    ai_config = tenant_config.get("ai_provider_config", default_ai_config.copy())
    
    # Mask AI key
    if ai_config.get("web_api_key"):
        ai_config["web_api_key"] = "********"
        
    # Get connectors
    notion_config = tenant_config.get("notion", default_notion_config.copy())
    slack_config = tenant_config.get("slack", default_slack_config.copy())
    
    # Ensure all keys exist
    for k, v in default_notion_config.items():
        if k not in notion_config:
            notion_config[k] = v
    for k, v in default_slack_config.items():
        if k not in slack_config:
            slack_config[k] = v
            
    # Mask connector keys
    if notion_config.get("api_key"):
        notion_config["api_key"] = "********"
    if slack_config.get("token"):
        slack_config["token"] = "********"
        
    return {
        "ai_provider": ai_provider,
        "config": ai_config,
        "connectors": {
            "notion": notion_config,
            "slack": slack_config
        }
    }

@router.post("/settings")
def update_settings(
    request: SettingsRequest,
    agent: dict = Depends(PermissionChecker(min_level=1))
):
    tenant_id = agent["tenant_id"]
    conn = get_tenant_connection(tenant_id)
    cursor = conn.cursor()
    
    cursor.execute("SELECT config FROM tenants WHERE id = ?", (tenant_id,))
    row = cursor.fetchone()
    if row and row["config"]:
        try:
            tenant_config = json.loads(row["config"])
        except Exception:
            tenant_config = {}
    else:
        tenant_config = {}
        
    # AI Provider update
    old_ai_config = tenant_config.get("ai_provider_config", {})
    new_ai_config = request.config
    
    # Handle key masking
    if new_ai_config.get("web_api_key") == "********":
        new_ai_config["web_api_key"] = old_ai_config.get("web_api_key", "")
        
    tenant_config["ai_provider"] = request.ai_provider
    tenant_config["ai_provider_config"] = new_ai_config
    
    # Connectors update
    if request.connectors:
        # Notion
        new_notion = request.connectors.get("notion", {})
        old_notion = tenant_config.get("notion", {})
        if new_notion:
            if new_notion.get("api_key") == "********":
                new_notion["api_key"] = old_notion.get("api_key", "")
            if "last_polled" not in new_notion or not new_notion["last_polled"]:
                new_notion["last_polled"] = old_notion.get("last_polled", "2000-01-01T00:00:00Z")
            tenant_config["notion"] = new_notion
            
        # Slack
        new_slack = request.connectors.get("slack", {})
        old_slack = tenant_config.get("slack", {})
        if new_slack:
            if new_slack.get("token") == "********":
                new_slack["token"] = old_slack.get("token", "")
            tenant_config["slack"] = new_slack
            
    cursor.execute(
        "UPDATE tenants SET config = ? WHERE id = ?",
        (json.dumps(tenant_config), tenant_id)
    )
    conn.commit()
    
    # Clear client cache
    from app.llm.kimi import _tenant_clients
    keys_to_del = [k for k in _tenant_clients.keys() if k.startswith(f"{tenant_id}_")]
    for k in keys_to_del:
        del _tenant_clients[k]
        
    return {
        "status": "success",
        "message": "Settings updated successfully",
        "ai_provider": request.ai_provider
    }

# ── POST /v1/notion/sync ─────────────────────────────────────────────────────

def run_notion_sync_background(tenant_id: str, job_id: str):
    """Background task: pull all pages/notes from Notion workspace and ingest them."""
    from app.ingestion.notion import NotionClient, sync_notion_metadata
    from app.ingestion.pipeline import run_ingestion_pipeline

    conn = get_tenant_connection(tenant_id)
    cursor = conn.cursor()

    try:
        cursor.execute("UPDATE ingestion_jobs SET status = 'processing', current_stage = 'notion_fetch' WHERE id = ?", (job_id,))
        conn.commit()

        # Load tenant config
        cursor.execute("SELECT config FROM tenants WHERE id = ?", (tenant_id,))
        row = cursor.fetchone()
        tenant_config = json.loads(row["config"]) if row and row["config"] else {}
        notion_cfg = tenant_config.get("notion", {})

        api_key = notion_cfg.get("api_key", "")
        database_id = notion_cfg.get("database_id", "").strip()
        last_polled = notion_cfg.get("last_polled", "2000-01-01T00:00:00Z")

        if not api_key:
            raise ValueError("Notion API key is not configured.")

        # Sync discovered metadata
        sync_notion_metadata(tenant_id, api_key)

        client = NotionClient(api_key=api_key)
        effective_db_id = database_id if database_id else ""
        messages = client.fetch_database_updates(effective_db_id, last_polled)

        if not messages:
            raise ValueError("No Notion pages were fetched. Check that the integration has access to your pages/databases.")

        pages_created = 0
        pages_meta = run_ingestion_pipeline(tenant_id, messages, job_id=job_id)
        pages_created = len(pages_meta)

        # Update status to 'synced' in notion_objects
        for p in pages_meta:
            for src in p.get("sources", []):
                if src.startswith("notion://page/"):
                    notion_id = src.split("/")[-1].split("#")[0]
                    cursor.execute(
                        "UPDATE notion_objects SET sync_status = 'synced', last_synced_at = ? WHERE notion_id = ?",
                        (datetime.datetime.utcnow().isoformat() + "Z", notion_id)
                    )

        # Update last_polled timestamp
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"
        notion_cfg["last_polled"] = now_iso
        tenant_config["notion"] = notion_cfg
        cursor.execute("UPDATE tenants SET config = ? WHERE id = ?", (json.dumps(tenant_config), tenant_id))
        cursor.execute(
            "UPDATE ingestion_jobs SET status = 'complete', completed_at = ?, pages_created = ? WHERE id = ?",
            (now_iso, pages_created, job_id)
        )
        conn.commit()

    except Exception as e:
        logger.error("notion_sync_failed", tenant_id=tenant_id, job_id=job_id, error=str(e))
        cursor.execute(
            "UPDATE ingestion_jobs SET status = 'failed', completed_at = ?, failure_reason = ? WHERE id = ?",
            (datetime.datetime.utcnow().isoformat() + "Z", str(e), job_id)
        )
        conn.commit()


@router.post("/notion/sync", status_code=status.HTTP_202_ACCEPTED)
def trigger_notion_sync(
    background_tasks: BackgroundTasks,
    agent: dict = Depends(PermissionChecker(min_level=1))
):
    """
    Manually trigger a full Notion sync.
    Pulls all pages, notes, plans, and docs from the connected Notion workspace
    (or a specific database if configured) and runs them through the ingestion pipeline.
    """
    tenant_id = agent["tenant_id"]
    conn = get_tenant_connection(tenant_id)
    cursor = conn.cursor()

    # Verify Notion is configured
    cursor.execute("SELECT config FROM tenants WHERE id = ?", (tenant_id,))
    row = cursor.fetchone()
    tenant_config = json.loads(row["config"]) if row and row["config"] else {}
    notion_cfg = tenant_config.get("notion", {})

    if not notion_cfg.get("api_key"):
        raise HTTPException(
            status_code=400,
            detail="Notion API key is not set. Please add your Notion token in Settings → Notion Sync and save first."
        )

    job_id = f"notion_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"

    cursor.execute(
        """
        INSERT INTO ingestion_jobs (id, tenant_id, status, source_type, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (job_id, tenant_id, "queued", "notion", now_iso)
    )
    conn.commit()

    background_tasks.add_task(run_notion_sync_background, tenant_id=tenant_id, job_id=job_id)

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Notion sync started. All workspace pages and notes will be ingested.",
        "poll_url": f"/v1/ingest/{job_id}"
    }


# ── GET /v1/graph ────────────────────────────────────────────────────────────

@router.get("/graph")
def get_graph(
    agent: dict = Depends(PermissionChecker(min_level=0))
):
    """
    Returns the tenant's page adjacency graph.
    Used by the frontend to render the interactive Obsidian-style network map.
    """
    tenant_id = agent["tenant_id"]
    tenant_dir = os.path.join(TENANTS_DIR, tenant_id)
    adj_path = os.path.join(tenant_dir, "graph", "adjacency.json")
    
    if not os.path.exists(adj_path):
        return {}
        
    try:
        with open(adj_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error("get_graph_error", tenant_id=tenant_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error loading graph: {e}"
        )


# ── Unified Sync Background Task ─────────────────────────────────────────────

def run_all_sync_background(tenant_id: str, job_id: str):
    """Background task: pull all pages/notes from all enabled connectors and ingest them."""
    from app.ingestion.notion import NotionClient, sync_notion_metadata
    from app.ingestion.pipeline import run_ingestion_pipeline

    conn = get_tenant_connection(tenant_id)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "UPDATE ingestion_jobs SET status = 'processing', current_stage = 'fetching_sources' WHERE id = ?",
            (job_id,)
        )
        conn.commit()

        # Load tenant config
        cursor.execute("SELECT config FROM tenants WHERE id = ?", (tenant_id,))
        row = cursor.fetchone()
        tenant_config = json.loads(row["config"]) if row and row["config"] else {}
        
        all_messages = []
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"
        
        # 1. Notion Sync if enabled
        notion_cfg = tenant_config.get("notion", {})
        if notion_cfg.get("enabled"):
            api_key = notion_cfg.get("api_key")
            database_id = notion_cfg.get("database_id", "").strip()
            last_polled = notion_cfg.get("last_polled", "2000-01-01T00:00:00Z")
            
            # Mask checks
            if api_key and api_key != "********":
                cursor.execute("UPDATE ingestion_jobs SET current_stage = 'notion_fetch' WHERE id = ?", (job_id,))
                conn.commit()
                
                # Discover & update metadata registry first
                sync_notion_metadata(tenant_id, api_key)
                
                client = NotionClient(api_key=api_key)
                effective_db_id = database_id if database_id else ""
                try:
                    notion_messages = client.fetch_database_updates(effective_db_id, last_polled)
                    if notion_messages:
                        all_messages.extend(notion_messages)
                    
                    # Update Notion polled timestamp
                    notion_cfg["last_polled"] = now_iso
                    tenant_config["notion"] = notion_cfg
                except Exception as ne:
                    logger.error("notion_sync_fetch_error", error=str(ne))

        # 2. Slack Sync if enabled
        slack_cfg = tenant_config.get("slack", {})
        if slack_cfg.get("enabled"):
            cursor.execute("UPDATE ingestion_jobs SET current_stage = 'slack_fetch' WHERE id = ?", (job_id,))
            conn.commit()
            
            # Generate simulated Slack message threads for the multi-connector demo.
            mock_slack_messages = [
                {
                    "text": "For deployment safety, let's document that Nginx reverse proxy worker timeouts should match gevent server configurations.",
                    "user": "slack_engineer_1",
                    "channel": slack_cfg.get("channel", "general"),
                    "timestamp": str(time.time()),
                    "source_id": f"slack://{slack_cfg.get('channel', 'general')}/{int(time.time())}"
                },
                {
                    "text": "Yes, we must set the worker timeout to at least 60 seconds because slow LLM query paths take time.",
                    "user": "slack_engineer_2",
                    "channel": slack_cfg.get("channel", "general"),
                    "timestamp": str(time.time() + 1),
                    "source_id": f"slack://{slack_cfg.get('channel', 'general')}/{int(time.time() + 1)}"
                }
            ]
            all_messages.extend(mock_slack_messages)

        # Fallback: if no active integrations are enabled, or no messages fetched, fail sync
        if not all_messages:
            raise ValueError("No Notion pages or Slack messages were fetched. Check that the integration has access to your pages/databases.")

        # Run pipeline
        pages_created = 0
        pages_meta = run_ingestion_pipeline(tenant_id, all_messages, job_id=job_id)
        pages_created = len(pages_meta)

        # Update status to 'synced' in notion_objects
        for p in pages_meta:
            for src in p.get("sources", []):
                if src.startswith("notion://page/"):
                    notion_id = src.split("/")[-1].split("#")[0]
                    cursor.execute(
                        "UPDATE notion_objects SET sync_status = 'synced', last_synced_at = ? WHERE notion_id = ?",
                        (datetime.datetime.utcnow().isoformat() + "Z", notion_id)
                    )

        # Save config update
        cursor.execute("UPDATE tenants SET config = ? WHERE id = ?", (json.dumps(tenant_config), tenant_id))
        real_completed_time = datetime.datetime.utcnow().isoformat() + "Z"
        cursor.execute(
            "UPDATE ingestion_jobs SET status = 'complete', completed_at = ?, pages_created = ? WHERE id = ?",
            (real_completed_time, pages_created, job_id)
        )
        conn.commit()

    except Exception as e:
        logger.error("all_sync_failed", tenant_id=tenant_id, job_id=job_id, error=str(e))
        cursor.execute(
            "UPDATE ingestion_jobs SET status = 'failed', completed_at = ?, failure_reason = ? WHERE id = ?",
            (datetime.datetime.utcnow().isoformat() + "Z", str(e), job_id)
        )
        conn.commit()


# ── POST /v1/sync/all ────────────────────────────────────────────────────────

@router.post("/sync/all", status_code=status.HTTP_202_ACCEPTED)
def trigger_all_sync(
    background_tasks: BackgroundTasks,
    agent: dict = Depends(PermissionChecker(min_level=1))
):
    """
    Triggers unified ingestion sync from all active connectors (Notion, Slack).
    Runs asynchronously and updates ingestion_jobs status with progress stages.
    """
    tenant_id = agent["tenant_id"]
    job_id = f"sync_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"

    conn = get_tenant_connection(tenant_id)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO ingestion_jobs (id, tenant_id, status, source_type, created_at, current_stage)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (job_id, tenant_id, "queued", "document", now_iso, "queued")
    )
    conn.commit()

    background_tasks.add_task(run_all_sync_background, tenant_id=tenant_id, job_id=job_id)

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Unified sync pipeline started.",
        "poll_url": f"/v1/ingest/{job_id}"
    }


# ── GET /v1/drafts ────────────────────────────────────────────────────────────

@router.get("/drafts")
def list_drafts(
    agent: dict = Depends(PermissionChecker(min_level=0))
):
    tenant_id = agent["tenant_id"]
    conn = get_tenant_connection(tenant_id)
    rows = conn.execute("SELECT * FROM knowledge_page_drafts").fetchall()
    return [dict(r) for r in rows]


# ── GET /v1/drafts/{draft_id} ──────────────────────────────────────────────────

@router.get("/drafts/{draft_id}")
def get_draft_by_id(
    draft_id: str,
    agent: dict = Depends(PermissionChecker(min_level=0))
):
    tenant_id = agent["tenant_id"]
    conn = get_tenant_connection(tenant_id)
    row = conn.execute("SELECT * FROM knowledge_page_drafts WHERE id = ?", (draft_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Draft not found")
    return dict(row)


# ── POST /v1/drafts/{draft_id}/approve ──────────────────────────────────────────

@router.post("/drafts/{draft_id}/approve")
def approve_draft_route(
    draft_id: str,
    agent: dict = Depends(PermissionChecker(min_level=1))
):
    tenant_id = agent["tenant_id"]
    approver = agent.get("email") or agent.get("id") or "approver"
    from app.ingestion.engine import CortexNewEngine
    engine = CortexNewEngine()
    result = engine.approve_draft(tenant_id, draft_id, approver)
    if not result.ok:
        raise HTTPException(status_code=400, detail=f"Approval failed: {', '.join(result.failures)}")
    return {
        "ok": True,
        "draft_id": result.draft_id,
        "page_id": result.page_id,
        "commit_sha": result.commit_sha
    }


# ── POST /v1/drafts/{draft_id}/reject ──────────────────────────────────────────

@router.post("/drafts/{draft_id}/reject")
def reject_draft_route(
    draft_id: str,
    agent: dict = Depends(PermissionChecker(min_level=1))
):
    tenant_id = agent["tenant_id"]
    conn = get_tenant_connection(tenant_id)
    row = conn.execute("SELECT 1 FROM knowledge_page_drafts WHERE id = ?", (draft_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Draft not found")
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    conn.execute(
        "UPDATE knowledge_page_drafts SET status = 'REJECTED', updated_at = ? WHERE id = ?",
        (now_iso, draft_id)
    )
    conn.commit()
    return {"ok": True, "draft_id": draft_id, "status": "REJECTED"}


# ── POST /v1/uploads ─────────────────────────────────────────────────────────
from fastapi import UploadFile, File

@router.post("/uploads", status_code=status.HTTP_202_ACCEPTED)
def upload_file_route(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    agent: dict = Depends(PermissionChecker(min_level=1))
):
    tenant_id = agent["tenant_id"]
    import tempfile
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}_{file.filename}")
    with open(temp_path, "wb") as f:
        f.write(file.file.read())
        
    job_id = f"job_upload_{uuid.uuid4().hex[:8]}"
    conn = get_tenant_connection(tenant_id)
    conn.execute(
        """
        INSERT INTO sync_runs (id, tenant_id, connector_type, status, started_at, completed_at, counts_json, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (job_id, tenant_id, "local_upload", "running", datetime.datetime.utcnow().isoformat() + "Z", None, "{}", None)
    )
    conn.commit()
    
    def process_upload(t_id: str, j_id: str, f_path: str, f_name: str):
        conn = get_tenant_connection(t_id)
        try:
            from app.ingestion.connectors.local_upload import LocalUploadAdapter
            from app.ingestion.engine import CortexNewEngine
            adapter = LocalUploadAdapter(t_id, f_path, filename=f_name)
            bundle = adapter.normalize()
            
            engine = CortexNewEngine(conn=conn)
            res = engine.ingest_bundle(t_id, bundle)
            
            doc_hashes = [doc.content_hash for doc in bundle.documents]
            segments_to_index = []
            for h in doc_hashes:
                doc_row = conn.execute("SELECT id FROM source_documents WHERE content_hash = ? AND tenant_id = ?", (h, t_id)).fetchone()
                if doc_row:
                    doc_id = doc_row["id"]
                    segs = conn.execute("SELECT id, text, content_hash FROM source_segments WHERE document_id = ? AND tenant_id = ?", (doc_id, t_id)).fetchall()
                    segments_to_index.extend([dict(r) for r in segs])
            
            if segments_to_index:
                from app.retrieval.raw_segment_index import RawSegmentIndex
                idx = RawSegmentIndex(t_id)
                idx.add_segments(segments_to_index)
            
            status = "completed" if res.ok else "failed"
            error_msg = ", ".join(res.failures) if not res.ok else None
            
            conn.execute(
                "UPDATE sync_runs SET status = ?, completed_at = ?, counts_json = ?, error_message = ? WHERE id = ?",
                (status, datetime.datetime.utcnow().isoformat() + "Z", json.dumps(res.counts), error_msg, j_id)
            )
            conn.commit()
        except Exception as e:
            conn.execute(
                "UPDATE sync_runs SET status = ?, completed_at = ?, error_message = ? WHERE id = ?",
                ("failed", datetime.datetime.utcnow().isoformat() + "Z", str(e), j_id)
            )
            conn.commit()
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)
                
    background_tasks.add_task(process_upload, tenant_id, job_id, temp_path, file.filename)
    return {
        "job_id": job_id,
        "status": "running",
        "message": "File upload started processing in background."
    }


# ── POST /v1/connectors/{connector_type}/sync ────────────────────────────────

@router.post("/connectors/{connector_type}/sync", status_code=status.HTTP_202_ACCEPTED)
def sync_connector_route(
    connector_type: str,
    background_tasks: BackgroundTasks,
    agent: dict = Depends(PermissionChecker(min_level=1))
):
    tenant_id = agent["tenant_id"]
    job_id = f"job_sync_{uuid.uuid4().hex[:8]}"
    
    conn = get_tenant_connection(tenant_id)
    conn.execute(
        """
        INSERT INTO sync_runs (id, tenant_id, connector_type, status, started_at, completed_at, counts_json, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (job_id, tenant_id, connector_type, "running", datetime.datetime.utcnow().isoformat() + "Z", None, "{}", None)
    )
    conn.commit()
    
    def process_sync(t_id: str, j_id: str, conn_type: str):
        conn = get_tenant_connection(t_id)
        try:
            bundle = None
            if conn_type == "notion":
                from app.ingestion.connectors.notion import NotionAdapter
                api_key = os.environ.get("NOTION_API_KEY", "mock_notion_key")
                adapter = NotionAdapter(t_id, api_key)
                bundle = adapter.normalize()
            elif conn_type == "slack":
                from app.ingestion.connectors.slack import SlackAdapter
                token = os.environ.get("SLACK_API_TOKEN", "mock_slack_token")
                adapter = SlackAdapter(t_id, token, ["C123"])
                bundle = adapter.normalize()
            elif conn_type == "google_docs":
                from app.ingestion.connectors.google_docs import GoogleDocsAdapter
                token = os.environ.get("GOOGLE_DOCS_TOKEN", "mock_gdocs_token")
                adapter = GoogleDocsAdapter(t_id, "doc_123", token)
                bundle = adapter.normalize()
            else:
                raise ValueError(f"Unknown connector type: {conn_type}")
                
            from app.ingestion.engine import CortexNewEngine
            engine = CortexNewEngine(conn=conn)
            res = engine.ingest_bundle(t_id, bundle)
            
            doc_hashes = [doc.content_hash for doc in bundle.documents]
            segments_to_index = []
            for h in doc_hashes:
                doc_row = conn.execute("SELECT id FROM source_documents WHERE content_hash = ? AND tenant_id = ?", (h, t_id)).fetchone()
                if doc_row:
                    doc_id = doc_row["id"]
                    segs = conn.execute("SELECT id, text, content_hash FROM source_segments WHERE document_id = ? AND tenant_id = ?", (doc_id, t_id)).fetchall()
                    segments_to_index.extend([dict(r) for r in segs])
            
            if segments_to_index:
                from app.retrieval.raw_segment_index import RawSegmentIndex
                idx = RawSegmentIndex(t_id)
                idx.add_segments(segments_to_index)
                
            status = "completed" if res.ok else "failed"
            error_msg = ", ".join(res.failures) if not res.ok else None
            conn.execute(
                "UPDATE sync_runs SET status = ?, completed_at = ?, counts_json = ?, error_message = ? WHERE id = ?",
                (status, datetime.datetime.utcnow().isoformat() + "Z", json.dumps(res.counts), error_msg, j_id)
            )
            conn.commit()
        except Exception as e:
            conn.execute(
                "UPDATE sync_runs SET status = ?, completed_at = ?, error_message = ? WHERE id = ?",
                ("failed", datetime.datetime.utcnow().isoformat() + "Z", str(e), j_id)
            )
            conn.commit()
            
    background_tasks.add_task(process_sync, tenant_id, job_id, connector_type)
    return {
        "job_id": job_id,
        "status": "running",
        "message": f"Sync run for {connector_type} started."
    }


# ── GET /v1/sync-runs/{sync_run_id} ──────────────────────────────────────────

@router.get("/sync-runs/{sync_run_id}")
def get_sync_run(
    sync_run_id: str,
    agent: dict = Depends(PermissionChecker(min_level=0))
):
    tenant_id = agent["tenant_id"]
    conn = get_tenant_connection(tenant_id)
    row = conn.execute("SELECT * FROM sync_runs WHERE id = ?", (sync_run_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Sync run not found")
    res = dict(row)
    res["counts"] = json.loads(res.pop("counts_json", "{}"))
    return res


# ── GET /v1/source-objects ───────────────────────────────────────────────────

@router.get("/source-objects")
def list_source_objects(
    agent: dict = Depends(PermissionChecker(min_level=0))
):
    tenant_id = agent["tenant_id"]
    conn = get_tenant_connection(tenant_id)
    rows = conn.execute("SELECT * FROM source_objects").fetchall()
    return [dict(r) for r in rows]


# ── GET /v1/source-documents/{document_id} ───────────────────────────────────

@router.get("/source-documents/{document_id}")
def get_source_document(
    document_id: str,
    agent: dict = Depends(PermissionChecker(min_level=0))
):
    tenant_id = agent["tenant_id"]
    conn = get_tenant_connection(tenant_id)
    row = conn.execute("SELECT * FROM source_documents WHERE id = ?", (document_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Source document not found")
    return dict(row)



