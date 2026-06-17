import os
import sys
import time
import yaml
from typing import Any, Dict, List, Optional, Tuple

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.llm.embedding import encode
from app.llm.kimi import get_kimi_client
from app.storage.hnsw_index import NumPyVectorIndex
from app.storage.graph import CortexGraph

def _load_page(pages_dir: str, page_id: str) -> Optional[Tuple[Dict[str, Any], str]]:
    """Reads a page file and returns its parsed YAML frontmatter and markdown body."""
    path = os.path.join(pages_dir, f"{page_id}.md")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            yaml_part = content[3:end].strip()
            body_part = content[end + 3:].strip()
            try:
                metadata = yaml.safe_load(yaml_part)
                return metadata, body_part
            except Exception:
                return {}, body_part
    return {}, content

class CortexQueryEngine:
    def __init__(self, tenant_dir: str, top_k: int = 3, similarity_threshold: float = 0.70):
        self.tenant_dir = tenant_dir
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold

        self.pages_dir = os.path.join(tenant_dir, "repo")
        index_path = os.path.join(tenant_dir, "vector_index.json")
        adjacency_path = os.path.join(tenant_dir, "graph", "adjacency.json")

        self.vector_index = NumPyVectorIndex(index_path=index_path, dim=384)
        self.graph = CortexGraph(adjacency_path=adjacency_path)

    def query(self, question: str, user_clearance: int = 1) -> Dict[str, Any]:
        """
        Executes a secure query over the tenant knowledge base.
        Filters out claims that exceed the user's authority level.
        """
        t_start = time.time()

        # 1. Embed question
        query_vector = encode(question)

        # 2. HNSW lookup -> entry pages
        vector_hits = self.vector_index.search(query_vector, k=self.top_k)
        entry_pages = [page_id for page_id, _ in vector_hits]

        # 3. BFS Traversal
        pages_to_read, traversal_path, knowledge_gaps = self.graph.traverse(
            entry_pages=entry_pages,
            query=question,
            vector_index=self.vector_index,
            query_vector=query_vector,
            similarity_threshold=self.similarity_threshold,
        )

        # 4. Load pages and apply claim-level security filtering
        context_blocks = []
        loaded_pages = []
        
        for page_id in pages_to_read:
            res = _load_page(self.pages_dir, page_id)
            if not res:
                continue
                
            metadata, body = res
            
            # Filter claims based on proposition sensitivity
            # Sensitivity levels:
            #   - public: require level >= 0
            #   - team: require level >= 1
            #   - confidential: require level >= 3
            propositions = metadata.get("propositions", [])
            filtered_body = body
            
            for prop in propositions:
                prop_text = prop.get("text", "")
                sens = prop.get("sensitivity", "team")
                
                # Check clearance requirements
                required_level = 0
                if sens == "team":
                    required_level = 1
                elif sens == "confidential":
                    required_level = 3
                    
                if user_clearance < required_level:
                    # User lacks authority; redact/remove this proposition text from the LLM context
                    filtered_body = filtered_body.replace(prop_text, "[REDACTED - INSUFFICIENT CLEARANCE]")
            
            context_blocks.append(f"=== Page [{page_id}] ===\n{filtered_body}")
            loaded_pages.append(page_id)

        # 5. LLM Answer Generation
        answer = self._generate_answer(question, context_blocks)
        total_ms = int((time.time() - t_start) * 1000)

        return {
            "answer": answer,
            "pages_read": loaded_pages,
            "traversal_path": traversal_path,
            "knowledge_gaps": knowledge_gaps,
            "total_latency_ms": total_ms,
            "pages_read_count": len(loaded_pages)
        }

    def _generate_answer(self, question: str, context_blocks: List[str]) -> str:
        if not context_blocks:
            return "No relevant knowledge pages found to answer this question."

        context = "\n\n".join(context_blocks)
        prompt = (
            "You are Cortex, a highly accurate corporate Knowledge OS assistant.\n"
            "The following are synthesized knowledge pages from the company's knowledge base.\n"
            "Use ONLY the information in these pages to answer the question.\n"
            "If the answer is not present or redacted, state that honestly.\n\n"
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
