import os
import json
from typing import List, Dict, Any, Tuple
from app.storage.hnsw_index import NumPyVectorIndex
from app.config import TENANTS_DIR
from app.llm.embedding import encode, encode_batch

class RawSegmentIndex:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.index_dir = os.path.join(TENANTS_DIR, tenant_id)
        os.makedirs(self.index_dir, exist_ok=True)
        self.index_path = os.path.join(self.index_dir, "raw_segment_index.json")
        self.hash_path = os.path.join(self.index_dir, "raw_segment_hashes.json")
        
        self.index = NumPyVectorIndex(index_path=self.index_path, dim=384)
        self.hashes = {}
        if os.path.exists(self.hash_path):
            try:
                with open(self.hash_path, "r", encoding="utf-8") as f:
                    self.hashes = json.load(f)
            except Exception:
                self.hashes = {}

    def add_segments(self, segments: List[Dict[str, Any]]):
        """Adds or updates segment embeddings in the index if content changed."""
        to_embed = []
        for s in segments:
            seg_id = f"segment:{s['id']}"
            h = s.get("content_hash") or s.get("content") or ""
            if seg_id not in self.index.page_ids or self.hashes.get(seg_id) != h:
                to_embed.append(s)

        if to_embed:
            texts = [s["text"] for s in to_embed]
            embeddings = encode_batch(texts)
            for s, emb in zip(to_embed, embeddings):
                seg_id = f"segment:{s['id']}"
                self.index.add_page(seg_id, emb)
                self.hashes[seg_id] = s.get("content_hash") or s.get("content") or ""
            
            self.index.save()
            with open(self.hash_path, "w", encoding="utf-8") as f:
                json.dump(self.hashes, f)

    def search(self, query_text: str, k: int = 3) -> List[Tuple[str, float]]:
        q_emb = encode(query_text)
        return self.index.search(q_emb, k=k)
