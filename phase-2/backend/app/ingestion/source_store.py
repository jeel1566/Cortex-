import json
import sqlite3
import uuid
from typing import Any, Dict, Iterable, List, Optional

from app.ingestion.engine_models import content_hash, utc_now


def _json(value: Any) -> str:
    return json.dumps(value or {}, sort_keys=True)


def _row(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def create_source_object(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    connector_type: str,
    external_id: str,
    object_type: str,
    title: str,
    url: str = "",
    author: str = "",
    raw_json: Optional[Dict[str, Any]] = None,
    content: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    now = utc_now()
    digest = content_hash(content or raw_json or title)
    existing = conn.execute(
        """
        SELECT * FROM source_objects
        WHERE tenant_id = ? AND connector_type = ? AND external_id = ?
        """,
        (tenant_id, connector_type, external_id),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE source_objects
            SET object_type = ?, title = ?, url = ?, author = ?, updated_at = ?,
                raw_json = ?, content_hash = ?, metadata_json = ?
            WHERE id = ?
            """,
            (object_type, title, url, author, now, _json(raw_json), digest, _json(metadata), existing["id"]),
        )
        conn.commit()
        return _row(conn.execute("SELECT * FROM source_objects WHERE id = ?", (existing["id"],)).fetchone())

    row_id = _new_id("srcobj")
    conn.execute(
        """
        INSERT INTO source_objects (
          id, tenant_id, connector_type, external_id, object_type, title, url,
          author, created_at, updated_at, raw_json, content_hash, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row_id,
            tenant_id,
            connector_type,
            external_id,
            object_type,
            title,
            url,
            author,
            now,
            now,
            _json(raw_json),
            digest,
            _json(metadata),
        ),
    )
    conn.commit()
    return _row(conn.execute("SELECT * FROM source_objects WHERE id = ?", (row_id,)).fetchone())


def find_source_object_by_hash(conn: sqlite3.Connection, tenant_id: str, digest: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM source_objects WHERE tenant_id = ? AND content_hash = ?",
        (tenant_id, digest),
    ).fetchone()
    return _row(row) if row else None


def create_source_document(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    source_object_id: str,
    title: str,
    body_text: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    now = utc_now()
    row_id = _new_id("srcdoc")
    conn.execute(
        """
        INSERT INTO source_documents (
          id, tenant_id, source_object_id, title, body_text, metadata_json,
          content_hash, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (row_id, tenant_id, source_object_id, title, body_text, _json(metadata), content_hash(body_text), now, now),
    )
    conn.commit()
    return _row(conn.execute("SELECT * FROM source_documents WHERE id = ?", (row_id,)).fetchone())


def create_source_segments(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    document_id: str,
    segments: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    now = utc_now()
    created = []
    for segment in segments:
        text = (segment.get("text") or "").strip()
        if not text:
            raise ValueError("source segment requires text")
        position = int(segment["position"])
        row_id = _new_id("srcseg")
        heading_path = segment.get("heading_path", "")
        if isinstance(heading_path, list):
            heading_path = " > ".join(heading_path)
        conn.execute(
            """
            INSERT INTO source_segments (
              id, tenant_id, document_id, segment_type, heading_path, position,
              text, author, timestamp, metadata_json, content_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row_id,
                tenant_id,
                document_id,
                segment.get("segment_type", "paragraph"),
                heading_path,
                position,
                text,
                segment.get("author"),
                segment.get("timestamp"),
                _json(segment.get("metadata")),
                segment.get("content_hash") or content_hash(f"{document_id}:{position}:{text}"),
                now,
            ),
        )
        created.append(row_id)
    conn.commit()
    return [_row(r) for r in conn.execute(
        f"SELECT * FROM source_segments WHERE id IN ({','.join('?' for _ in created)}) ORDER BY position",
        created,
    ).fetchall()]


def list_source_segments(conn: sqlite3.Connection, document_id: str) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM source_segments WHERE document_id = ? ORDER BY position",
        (document_id,),
    ).fetchall()
    return [_row(r) for r in rows]


def create_source_relationship(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    from_object_id: str,
    to_object_id: str,
    relationship_type: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    row_id = _new_id("srcrel")
    conn.execute(
        """
        INSERT INTO source_relationships (
          id, tenant_id, from_object_id, to_object_id, relationship_type,
          metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (row_id, tenant_id, from_object_id, to_object_id, relationship_type, _json(metadata), utc_now()),
    )
    conn.commit()
    return _row(conn.execute("SELECT * FROM source_relationships WHERE id = ?", (row_id,)).fetchone())


def create_knowledge_page_draft(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    title: str,
    content: str,
    status: str = "DRAFT",
    validation_passed: bool = False,
    errors: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    now = utc_now()
    row_id = _new_id("draft")
    conn.execute(
        """
        INSERT INTO knowledge_page_drafts (
          id, tenant_id, title, content, status, validation_passed, errors_json,
          warnings_json, validated_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row_id,
            tenant_id,
            title,
            content,
            status,
            1 if validation_passed else 0,
            json.dumps(errors or []),
            json.dumps(warnings or []),
            now if validation_passed else None,
            now,
            now,
        ),
    )
    conn.commit()
    return _row(conn.execute("SELECT * FROM knowledge_page_drafts WHERE id = ?", (row_id,)).fetchone())


def get_draft(conn: sqlite3.Connection, tenant_id: str, draft_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM knowledge_page_drafts WHERE tenant_id = ? AND id = ?",
        (tenant_id, draft_id),
    ).fetchone()
    return _row(row) if row else None


def mark_draft_approved(conn: sqlite3.Connection, tenant_id: str, draft_id: str) -> None:
    conn.execute(
        "UPDATE knowledge_page_drafts SET status = 'APPROVED', updated_at = ? WHERE tenant_id = ? AND id = ?",
        (utc_now(), tenant_id, draft_id),
    )
    conn.commit()
