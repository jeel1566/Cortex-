import time
import datetime
import threading
import json
from typing import Dict, Any

from app.database.connection import get_tenant_connection
from app.ingestion.notion import NotionClient
from app.ingestion.pipeline import run_ingestion_pipeline
from app.logging import get_logger

logger = get_logger(__name__)

class IngestionQueueWorker:
    """
    Background worker that runs polling loops for Notion data sources.
    Enforces the 5-minute (or configurable) freshness schedule.
    """
    def __init__(self, poll_interval_sec: int = 300):
        self.poll_interval_sec = poll_interval_sec
        self.is_running = False
        self._thread = None

    def start(self):
        """Starts the background polling thread."""
        self.is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("ingestion_worker_started", interval_sec=self.poll_interval_sec)

    def stop(self):
        """Stops the background polling thread."""
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("ingestion_worker_stopped")

    def _run_loop(self):
        while self.is_running:
            try:
                self.poll_all_tenants()
            except Exception as e:
                logger.error("polling_loop_error", error=str(e))
            time.sleep(self.poll_interval_sec)

    def poll_all_tenants(self):
        """
        Scans all configured tenants in SQLite and runs Notion polling
        for those with active configurations.
        """
        # Since we use tenant-specific DBs, we can get list of active tenants from the filesystem
        # or config. For MVP, we inspect the tenants directory.
        from app.config import TENANTS_DIR
        if not os.path.exists(TENANTS_DIR):
            return
            
        tenant_ids = [d for d in os.listdir(TENANTS_DIR) if os.path.isdir(os.path.join(TENANTS_DIR, d))]
        
        for tenant_id in tenant_ids:
            try:
                conn = get_tenant_connection(tenant_id)
                cursor = conn.cursor()
                
                # Check for active Notion configuration inside the database
                # (For MVP, we query a simple key-value config table or just metadata)
                cursor.execute("SELECT config FROM tenants WHERE id = ?", (tenant_id,))
                row = cursor.fetchone()
                if not row or not row["config"]:
                    continue
                    
                config = json.loads(row["config"])
                notion_config = config.get("notion", {})
                if not notion_config.get("enabled", False):
                    continue
                    
                database_id = notion_config.get("database_id")
                last_polled = notion_config.get("last_polled", "2026-06-01T00:00:00Z")
                
                logger.info("polling_notion", tenant_id=tenant_id, database_id=database_id)
                
                client = NotionClient(api_key=notion_config.get("api_key"))
                updates = client.fetch_database_updates(database_id, last_polled)
                
                if updates:
                    logger.info("notion_updates_found", tenant_id=tenant_id, count=len(updates))
                    run_ingestion_pipeline(tenant_id, updates)
                    
                # Update last polled time
                now_str = datetime.datetime.utcnow().isoformat() + "Z"
                notion_config["last_polled"] = now_str
                config["notion"] = notion_config
                
                cursor.execute(
                    "UPDATE tenants SET config = ? WHERE id = ?",
                    (json.dumps(config), tenant_id)
                )
                conn.commit()
                
            except Exception as e:
                logger.error("tenant_poll_failed", tenant_id=tenant_id, error=str(e))

import os
