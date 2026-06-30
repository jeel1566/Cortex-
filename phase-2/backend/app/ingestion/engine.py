import os
from typing import Dict, List, Optional

from app.database.connection import get_tenant_connection
from app.ingestion.engine_models import (
    ApprovalResult,
    DraftCompileResult,
    EngineIngestResult,
    EngineStageResult,
    NormalizedSourceBundle,
)
from app.ingestion.source_store import (
    create_knowledge_page_draft,
    create_source_document,
    create_source_object,
    create_source_relationship,
    create_source_segments,
    get_draft,
    mark_draft_approved,
)
from app.ingestion.validation import verify_page_shape


class CortexNewEngine:
    def __init__(self, conn=None):
        self.conn = conn

    def _conn(self, tenant_id: str):
        return self.conn or get_tenant_connection(tenant_id)

    def ingest_bundle(self, tenant_id: str, bundle: NormalizedSourceBundle) -> EngineIngestResult:
        if tenant_id != bundle.tenant_id:
            raise ValueError("tenant_id does not match source bundle")

        conn = self._conn(tenant_id)
        counts = {
            "objects": 0,
            "documents": 0,
            "segments": 0,
            "relationships": 0,
            "drafts": 0,
            "skipped_empty": getattr(bundle, "skipped_empty_count", 0)
        }
        stages: List[EngineStageResult] = []

        object_ids: Dict[str, str] = {}
        for source_object in bundle.objects:
            row = create_source_object(
                conn,
                tenant_id=tenant_id,
                connector_type=source_object.connector_type,
                external_id=source_object.external_id,
                object_type=source_object.object_type,
                title=source_object.title,
                url=source_object.url or "",
                author=source_object.author or "",
                raw_json=source_object.raw_json,
                content=source_object.content_hash,
                metadata=source_object.metadata,
            )
            object_ids[source_object.external_id] = row["id"]
        counts["objects"] = len(object_ids)
        stages.append(EngineStageResult(stage="store_source_objects", ok=True, counts={"objects": counts["objects"]}))

        document_ids: Dict[str, str] = {}
        for document in bundle.documents:
            source_object_id = object_ids.get(document.source_object_external_id)
            if not source_object_id:
                raise ValueError(f"missing source object for document: {document.source_object_external_id}")
            row = create_source_document(
                conn,
                tenant_id=tenant_id,
                source_object_id=source_object_id,
                title=document.title,
                body_text=document.body_text,
                metadata=document.metadata,
            )
            document_ids[document.source_object_external_id] = row["id"]
        counts["documents"] = len(document_ids)

        segment_rows = []
        for source_object_external_id, document_id in document_ids.items():
            segments = [
                s.model_dump()
                for s in bundle.segments
                if s.document_ref == source_object_external_id
            ]
            segment_rows.extend(
                create_source_segments(conn, tenant_id=tenant_id, document_id=document_id, segments=segments)
            )
        counts["segments"] = len(segment_rows)
        stages.append(
            EngineStageResult(
                stage="store_source_documents",
                ok=True,
                counts={"documents": counts["documents"], "segments": counts["segments"]},
            )
        )

        for relationship in bundle.relationships:
            from_id = object_ids.get(relationship.from_external_id)
            to_id = object_ids.get(relationship.to_external_id)
            if from_id and to_id:
                create_source_relationship(
                    conn,
                    tenant_id=tenant_id,
                    from_object_id=from_id,
                    to_object_id=to_id,
                    relationship_type=relationship.relationship_type,
                    metadata=relationship.metadata,
                )
                counts["relationships"] += 1
        stages.append(EngineStageResult(stage="store_source_relationships", ok=True, counts={"relationships": counts["relationships"]}))

        draft_result = self._compile_minimal_drafts(conn, tenant_id, bundle)
        counts["drafts"] = len(draft_result.draft_ids)
        stages.append(EngineStageResult(stage="compile_drafts", ok=draft_result.ok, counts={"drafts": counts["drafts"]}, failures=draft_result.failures))

        return EngineIngestResult(tenant_id=tenant_id, ok=draft_result.ok, stage_results=stages, counts=counts, failures=draft_result.failures)

    def _compile_minimal_drafts(self, conn, tenant_id: str, bundle: NormalizedSourceBundle) -> DraftCompileResult:
        import uuid
        import json
        from app.ingestion.compiler import DraftCompiler
        from app.ingestion.engine_models import utc_now
        
        compiler = DraftCompiler()
        draft_ids = []
        failures = []
        for document in bundle.documents:
            source_segments = [s for s in bundle.segments if s.document_ref == document.source_object_external_id]
            res = compiler.compile_draft(tenant_id, document, source_segments)
            
            status = "DRAFT" if res["validation_passed"] else "REJECTED"
            draft = create_knowledge_page_draft(
                conn,
                tenant_id=tenant_id,
                title=document.title,
                content=res["content"],
                status=status,
                validation_passed=res["validation_passed"],
                errors=res["errors"],
            )
            draft_ids.append(draft["id"])
            
            if res["validation_passed"]:
                for p in res["propositions"]:
                    conn.execute(
                        """
                        INSERT INTO propositions (id, tenant_id, draft_id, text, evidence_segment_ids_json, sensitivity, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            f"prop_{uuid.uuid4().hex[:8]}",
                            tenant_id,
                            draft["id"],
                            p["text"],
                            json.dumps(p["evidence_segment_ids"]),
                            p.get("sensitivity", "team"),
                            utc_now()
                        )
                    )
                conn.commit()
            else:
                failures.extend(res["errors"])
        return DraftCompileResult(ok=not failures, draft_ids=draft_ids, failures=failures)

    def approve_draft(self, tenant_id: str, draft_id: str, approver: str) -> ApprovalResult:
        from app.storage.git_store import commit_page_changes, get_tenant_repo_dir, init_tenant_repo

        conn = self._conn(tenant_id)
        draft = get_draft(conn, tenant_id, draft_id)
        if not draft:
            return ApprovalResult(ok=False, draft_id=draft_id, failures=["draft not found"])

        try:
            verify_page_shape(draft["content"])
        except ValueError as exc:
            return ApprovalResult(ok=False, draft_id=draft_id, failures=[str(exc)])

        init_tenant_repo(tenant_id)
        repo_dir = get_tenant_repo_dir(tenant_id)
        page_id = draft_id.replace("draft_", "page_", 1)
        page_path = os.path.join(repo_dir, f"{page_id}.md")
        with open(page_path, "w", encoding="utf-8") as page_file:
            page_file.write(draft["content"])

        commit_sha = commit_page_changes(tenant_id, page_id, f"approve: {page_id} by {approver}")
        mark_draft_approved(conn, tenant_id, draft_id)

        try:
            from app.llm.embedding import encode
            from app.storage.hnsw_index import NumPyVectorIndex
            from app.config import TENANTS_DIR
            
            body = draft["content"]
            if body.startswith("---"):
                from app.ingestion.validation import find_frontmatter_end
                close = find_frontmatter_end(body)
                if close != -1:
                    body = body[close+3:].strip()
            
            emb = encode(body)
            index_path = os.path.join(TENANTS_DIR, tenant_id, "vector_index.json")
            vector_index = NumPyVectorIndex(index_path=index_path, dim=384)
            vector_index.add_page(page_id, emb)
            vector_index.save()
        except Exception as e:
            print(f"Error indexing approved page: {e}")

        return ApprovalResult(ok=True, draft_id=draft_id, page_id=page_id, commit_sha=commit_sha)
