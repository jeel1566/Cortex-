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

QUERIES_COUNTER = Counter("cortex_queries_total", "Total queries executed", ["tenant_id"])
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
    clearance = agent["authority_level"]
    question = request.question
    
    tenant_dir = os.path.join(TENANTS_DIR, tenant_id)
    if not os.path.exists(tenant_dir):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant repository has not been initialized. No pages exist."
        )
        
    try:
        t0 = time.time()
        engine = CortexQueryEngine(tenant_dir=tenant_dir)
        result = engine.query(question, user_clearance=clearance)
        latency_sec = time.time() - t0
        QUERIES_COUNTER.labels(tenant_id=tenant_id).inc()
        LATENCY_HISTOGRAM.labels(tenant_id=tenant_id).observe(latency_sec)
    except Exception as e:
        logger.error("query_error", tenant_id=tenant_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error running query: {e}"
        )
        
    # Log the query execution to the tenant's SQLite DB
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
                result["total_latency_ms"],
                clearance,
                0.90,  # overall_confidence mock
                0,     # had_conflict
                1 if len(result["knowledge_gaps"]) > 0 else 0,
                datetime.datetime.utcnow().isoformat() + "Z"
            )
        )
        conn.commit()
    except Exception as e:
        logger.error("query_log_error", error=str(e))
        
    return {
        "query_id": query_id,
        "pages": [
            {
                "id": pid,
                "title": f"Page {pid}",
                "content": f"Context block retrieved for {pid}"
            } for pid in result["pages_read"]
        ],
        "traversal_path": result["traversal_path"],
        "knowledge_gaps": result["knowledge_gaps"],
        "overall_confidence": 0.90,
        "total_latency_ms": result["total_latency_ms"],
        "pages_read": len(result["pages_read"])
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
    from app.ingestion.notion import NotionClient
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

        client = NotionClient(api_key=api_key)

        # If no database_id — search entire workspace (all pages/notes/docs)
        effective_db_id = database_id if database_id else ""
        messages = client.fetch_database_updates(effective_db_id, last_polled)

        pages_created = 0
        if messages:
            pages_created = run_ingestion_pipeline(tenant_id, messages, job_id=job_id)

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
            "UPDATE ingestion_jobs SET status = 'failed', completed_at = ? WHERE id = ?",
            (datetime.datetime.utcnow().isoformat() + "Z", job_id)
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
