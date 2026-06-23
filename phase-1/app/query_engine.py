"""
Cortex Query Engine — app/query_engine.py

Implements the query path described in the architecture:
  1. Embed the question (fastembed, BAAI/bge-small-en-v1.5)
  2. HNSW vector index lookup → top-k candidate page IDs
  3. Two-phase BFS graph traversal (primary then secondary links)
  4. Assemble page content
  5. Call the configured LLM (local_ai / web_api / coding_agent) for the answer
"""

import os
import sys
import json
import time
from typing import Any, Dict, List, Optional, Tuple

# Allow running from project root or phase-1/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.llm.embedding import encode
from app.llm.kimi import get_kimi_client
from app.storage.hnsw_index import NumPyVectorIndex
from app.storage.graph import CortexGraph
from app.ingestion.alias_resolver import load_alias_map


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_page(pages_dir: str, page_id: str) -> Optional[str]:
    """Read a page markdown file and return its full text content."""
    path = os.path.join(pages_dir, f"{page_id}.md")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _strip_yaml_header(content: str) -> str:
    """Strip the YAML frontmatter block (--- ... ---) from a page, keeping only body."""
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            return content[end + 3:].strip()
    return content


# ---------------------------------------------------------------------------
# CortexQueryEngine
# ---------------------------------------------------------------------------

class CortexQueryEngine:
    """
    End-to-end Cortex query engine.

    Args:
        tenant_dir: Root directory for the tenant knowledge store.
                    Expected layout:
                      <tenant_dir>/
                        os/
                          pages/              <- page_xxx.md files
                          graph/adjacency.json
                          vector_index.json
        top_k: Number of entry pages returned by the HNSW search.
        similarity_threshold: Minimum cosine similarity for graph safety-net.
    """

    def __init__(
        self,
        tenant_dir: str,
        top_k: int = 3,
        similarity_threshold: float = 0.70,
    ):
        self.tenant_dir = tenant_dir
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold

        self.pages_dir   = os.path.join(tenant_dir, "os", "pages")
        index_path       = os.path.join(tenant_dir, "os", "vector_index.json")
        adjacency_path   = os.path.join(tenant_dir, "os", "graph", "adjacency.json")

        print("[CortexQueryEngine] Loading vector index...")
        self.vector_index = NumPyVectorIndex(index_path=index_path, dim=384)
        print(f"[CortexQueryEngine] Index has {len(self.vector_index.page_ids)} pages.")

        print("[CortexQueryEngine] Loading graph adjacency...")
        self.graph = CortexGraph(adjacency_path=adjacency_path)
        print(f"[CortexQueryEngine] Graph has {len(self.graph.graph)} nodes.")

        # Load alias map for query-time alias expansion
        alias_path = os.path.join(tenant_dir, "os", "alias_map.json")
        self.alias_map = load_alias_map(alias_path)
        if self.alias_map:
            print(f"[CortexQueryEngine] Loaded aliases for {len(self.alias_map)} users.")

    # ------------------------------------------------------------------
    def query(self, question: str) -> Dict[str, Any]:
        """
        Run an end-to-end Cortex query.

        Returns a dict:
            {
              "answer": str,
              "pages_read": List[str],
              "traversal_path": List[dict],
              "knowledge_gaps": List[str],
              "total_latency_ms": int,
              "pages_read_count": int,
            }
        """
        t_start = time.time()

        # 0. Expand query with known aliases
        expanded_question = self._expand_query_with_aliases(question)

        # 1. Embed question (use expanded version for better retrieval)
        t0 = time.time()
        query_vector = encode(expanded_question)
        t_embed = (time.time() - t0) * 1000

        # 2. HNSW lookup -> entry page candidates
        t0 = time.time()
        vector_hits = self.vector_index.search(query_vector, k=self.top_k)
        entry_pages = [page_id for page_id, _ in vector_hits]
        t_hnsw = (time.time() - t0) * 1000

        # 3. Two-phase BFS graph traversal
        t0 = time.time()
        pages_to_read, traversal_path, knowledge_gaps = self.graph.traverse(
            entry_pages=entry_pages,
            query=question,
            vector_index=self.vector_index,
            query_vector=query_vector,
            similarity_threshold=self.similarity_threshold,
        )
        t_traverse = (time.time() - t0) * 1000

        # 4. Assemble page content
        t0 = time.time()
        context_blocks = []
        loaded_pages = []
        for page_id in pages_to_read:
            content = _load_page(self.pages_dir, page_id)
            if content:
                body = _strip_yaml_header(content)
                context_blocks.append(f"=== Page [{page_id}] ===\n{body}")
                loaded_pages.append(page_id)
        t_assemble = (time.time() - t0) * 1000

        # 5. LLM generation
        t0 = time.time()
        answer = self._generate_answer(question, context_blocks)
        t_gen = (time.time() - t0) * 1000

        total_ms = int((time.time() - t_start) * 1000)

        print(f"\n--- Cortex Query Latency ---")
        print(f"  Question       : {question[:80]}")
        print(f"  Embed          : {t_embed:.1f} ms")
        print(f"  HNSW lookup    : {t_hnsw:.1f} ms  (entry pages: {entry_pages})")
        print(f"  Graph traversal: {t_traverse:.1f} ms  (pages: {pages_to_read})")
        print(f"  Assemble       : {t_assemble:.1f} ms  (loaded: {len(loaded_pages)})")
        print(f"  LLM generation : {t_gen:.1f} ms")
        print(f"  TOTAL          : {total_ms} ms")
        print(f"----------------------------\n")

        return {
            "answer": answer,
            "pages_read": loaded_pages,
            "traversal_path": traversal_path,
            "knowledge_gaps": knowledge_gaps,
            "total_latency_ms": total_ms,
            "pages_read_count": len(loaded_pages),
        }

    # ------------------------------------------------------------------
    def _expand_query_with_aliases(self, question: str) -> str:
        if not self.alias_map:
            return question
        q_low = question.lower()
        notes = []
        for names in self.alias_map.values():
            for n in names:
                if n.lower() in q_low:
                    others = [x for x in names if x.lower() != n.lower()]
                    if others:
                        notes.append(f"(Note: {n} is also known as {', '.join(others)})")
                    break
        return f"{question} {' '.join(notes)}" if notes else question

    # ------------------------------------------------------------------
    def _generate_answer(self, question: str, context_blocks: List[str]) -> str:
        if not context_blocks:
            return "No relevant knowledge pages found to answer this question."

        context = "\n\n".join(context_blocks)
        prompt = (
            "You are Cortex, a highly accurate corporate Knowledge OS assistant.\n"
            "The following are synthesized knowledge pages from the company's knowledge base.\n"
            "Use ONLY the information in these pages to answer the question.\n"
            "If the answer is not present, state that honestly.\n\n"
            "=== KNOWLEDGE PAGES ===\n"
            f"{context}\n\n"
            f"Question: {question}\n\n"
            "Answer:"
        )
        try:
            client = get_kimi_client()
            return client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1024,
            )
        except Exception as e:
            return f"Error generating answer: {e}"


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Cortex Query Engine test")
    parser.add_argument("--tenant-dir", default="d:/Cortex/phase-1/data/tenants/default")
    parser.add_argument("question", nargs="?", default="Who started Superset and when?")
    args = parser.parse_args()

    engine = CortexQueryEngine(tenant_dir=args.tenant_dir)
    result = engine.query(args.question)
    print("Answer:", result["answer"])
    print("Pages read:", result["pages_read"])
