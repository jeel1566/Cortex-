import os
import time
import json
import sqlite3
from typing import Dict, Any, List
from app.database.connection import get_tenant_connection
from app.retrieval.raw_segment_index import RawSegmentIndex
from app.retrieval.permissions import check_permission
from app.storage.hnsw_index import NumPyVectorIndex
from app.storage.graph import CortexGraph
from app.llm.kimi import get_kimi_client

class HybridQueryEngine:
    def __init__(self, tenant_id: str, conn=None):
        self.tenant_id = tenant_id
        from app.config import TENANTS_DIR
        self.tenant_dir = os.path.join(TENANTS_DIR, tenant_id)
        self.conn = conn or get_tenant_connection(tenant_id)
        self.raw_segment_index = RawSegmentIndex(tenant_id)
        
        self.pages_dir = os.path.join(self.tenant_dir, "repo")
        self.vector_index = NumPyVectorIndex(index_path=os.path.join(self.tenant_dir, "vector_index.json"), dim=384)
        self.graph = CortexGraph(adjacency_path=os.path.join(self.tenant_dir, "graph", "adjacency.json"))

    def query(self, question: str, user: Dict[str, Any]) -> Dict[str, Any]:
        t_start = time.time()
        
        from app.llm.embedding import encode
        q_emb = encode(question)
        page_hits = self.vector_index.search(q_emb, k=3)
        segment_hits = self.raw_segment_index.search(question, k=5)
        
        segment_ids = [s_id.replace("segment:", "", 1) for s_id, _ in segment_hits]
        segments_data = []
        if segment_ids:
            placeholders = ",".join("?" for _ in segment_ids)
            cursor = self.conn.execute(
                f"SELECT * FROM source_segments WHERE id IN ({placeholders})",
                segment_ids
            )
            segments_data = [dict(row) for row in cursor.fetchall()]
            
        allowed_pages = []
        allowed_segments = []
        redactions = []
        
        for page_id, sim in page_hits:
            path = os.path.join(self.pages_dir, f"{page_id}.md")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                access_level = "team"
                dept = None
                if content.startswith("---"):
                    end = content.find("---", 3)
                    if end != -1:
                        try:
                            import yaml
                            meta = yaml.safe_load(content[3:end].strip())
                            access_level = meta.get("access_level", "team")
                            dept = meta.get("department")
                        except Exception:
                            pass
                if check_permission(user, access_level, dept):
                    allowed_pages.append(page_id)
                else:
                    redactions.append(f"page:{page_id}")
                    
        for seg in segments_data:
            meta = json.loads(seg.get("metadata_json", "{}"))
            access_level = meta.get("access_level", "team")
            dept = meta.get("department")
            if check_permission(user, access_level, dept):
                allowed_segments.append(seg)
            else:
                redactions.append(f"segment:{seg['id']}")
                
        context_parts = []
        for page_id in allowed_pages:
            path = os.path.join(self.pages_dir, f"{page_id}.md")
            with open(path, "r", encoding="utf-8") as f:
                context_parts.append(f"Approved Page {page_id}:\n{f.read()}")
                
        for seg in allowed_segments:
            context_parts.append(f"Raw Evidence Segment {seg['id']}:\n{seg['text']}")
            
        context_str = "\n\n".join(context_parts)
        
        answer = "No evidence found to answer the question."
        if context_str:
            client = get_kimi_client(self.tenant_id)
            messages = [
                {"role": "system", "content": "You are a trusted knowledge assistant. Answer the user's question based strictly on the provided context. Cite your sources."},
                {"role": "user", "content": f"Context:\n{context_str}\n\nQuestion: {question}"}
            ]
            try:
                answer = client.chat_completion(messages, temperature=0.1)
            except Exception as e:
                answer = f"Error generating answer: {e}"
                
        citations = []
        for p in allowed_pages:
            citations.append(f"page:{p}")
        for s in allowed_segments:
            citations.append(f"segment:{s['id']}")
            
        knowledge_gaps = []
        if not allowed_pages and not allowed_segments:
            knowledge_gaps.append("No matching canonical knowledge or raw source evidence found.")
            
        latency = int((time.time() - t_start) * 1000)
        
        return {
            "answer": answer,
            "citations": citations,
            "pages_read": allowed_pages,
            "source_segments_read": [s["id"] for s in allowed_segments],
            "redactions": redactions,
            "knowledge_gaps": knowledge_gaps,
            "confidence": 0.9 if allowed_pages else 0.5,
            "latency_ms": latency
        }
