from typing import List, Dict, Any, Optional
import sqlite3
from app.ingestion.source_store import create_knowledge_page_draft, get_draft, mark_draft_approved

def save_draft(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    title: str,
    content: str,
    validation_passed: bool = False,
    errors: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return create_knowledge_page_draft(
        conn,
        tenant_id=tenant_id,
        title=title,
        content=content,
        status="DRAFT" if validation_passed else "REJECTED",
        validation_passed=validation_passed,
        errors=errors,
        warnings=warnings,
    )
