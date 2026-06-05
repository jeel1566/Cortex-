import os
import re
import json
import time
from typing import List, Dict, Any, Tuple, Set

class CortexGraph:
    """
    In-memory graph store representing knowledge page adjacency relationships.
    Supports primary links and conditional secondary links.
    """
    def __init__(self, adjacency_path: str = None):
        self.adjacency_path = adjacency_path
        # Map: page_id -> {"primary": [page_ids], "secondary": [{"condition": str, "page": page_id}]}
        self.graph = {}
        
        if adjacency_path and os.path.exists(adjacency_path):
            self.load()
            
    def add_link(self, from_page: str, to_page: str, link_type: str = "primary", condition: str = None):
        """Adds a primary or secondary link to the graph."""
        if from_page not in self.graph:
            self.graph[from_page] = {"primary": [], "secondary": []}
            
        if link_type == "primary":
            if to_page not in self.graph[from_page]["primary"]:
                self.graph[from_page]["primary"].append(to_page)
        elif link_type == "secondary":
            if not condition:
                raise ValueError("Secondary links require a condition string.")
            # Check if this secondary link already exists
            exists = any(item["page"] == to_page and item["condition"] == condition 
                         for item in self.graph[from_page]["secondary"])
            if not exists:
                self.graph[from_page]["secondary"].append({
                    "condition": condition,
                    "page": to_page
                })
                
    def match_condition(self, condition_str: str, query: str) -> bool:
        """Evaluates whether the user query satisfies a secondary link condition."""
        if not condition_str or not query:
            return False
            
        query_clean = query.lower()
        cond_clean = condition_str.lower()
        
        # Simple logical parsing: check ' or ' and ' and '
        if ' or ' in cond_clean:
            parts = [p.strip() for p in cond_clean.split(' or ')]
            return any(p in query_clean for p in parts if p)
        elif ' and ' in cond_clean:
            parts = [p.strip() for p in cond_clean.split(' and ')]
            return all(p in query_clean for p in parts if p)
        else:
            return cond_clean in query_clean

    def traverse(self, 
                 entry_pages: List[str], 
                 query: str, 
                 vector_index: Any = None, 
                 query_vector: List[float] = None, 
                 similarity_threshold: float = 0.70) -> Tuple[List[str], List[Dict[str, Any]], List[str]]:
        """
        Performs a two-phase BFS traversal.
        Phase 1: Exhaust primary links.
        Phase 2: Evaluate and follow conditional secondary links.
        Fallback: Run vector safety net to catch orphans.
        
        Returns:
            pages_to_read: list of page IDs to return.
            traversal_path: list of traversal step dicts for audit.
            knowledge_gaps: list of detected gaps or missing links.
        """
        visited: Set[str] = set()
        traversal_path: List[Dict[str, Any]] = []
        pages_to_read: List[str] = []
        
        # Queue for BFS traversal
        queue: List[str] = list(entry_pages)
        for page in entry_pages:
            visited.add(page)
            pages_to_read.append(page)
            
        # Phase 1: Exhaust primary links from entry pages
        idx = 0
        while idx < len(queue):
            current_page = queue[idx]
            idx += 1
            
            # Follow primary links
            neighbors = self.graph.get(current_page, {}).get("primary", [])
            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    pages_to_read.append(neighbor)
                    queue.append(neighbor)
                    traversal_path.append({
                        "from": current_page,
                        "to": neighbor,
                        "link_type": "primary",
                        "condition_matched": "always"
                    })
                    
        # Phase 2: Follow secondary links if conditions match the query
        # We look at all visited nodes so far and check their secondary links
        secondary_queue = list(pages_to_read)
        sec_idx = 0
        while sec_idx < len(secondary_queue):
            current_page = secondary_queue[sec_idx]
            sec_idx += 1
            
            secondary_links = self.graph.get(current_page, {}).get("secondary", [])
            for item in secondary_links:
                cond = item["condition"]
                target = item["page"]
                
                if target not in visited:
                    if self.match_condition(cond, query):
                        visited.add(target)
                        pages_to_read.append(target)
                        secondary_queue.append(target)
                        traversal_path.append({
                            "from": current_page,
                            "to": target,
                            "link_type": "secondary",
                            "condition_matched": cond
                        })
                        
        # Step 4: Vector Safety Net Fallback
        knowledge_gaps = []
        if vector_index and query_vector:
            # Search database for similar pages
            vector_results = vector_index.search(query_vector, k=5)
            
            for page_id, similarity in vector_results:
                if similarity >= similarity_threshold:
                    if page_id not in visited:
                        # Page is highly relevant but was not reached by graph traversal
                        print(f"Safety net caught orphan page: {page_id} (similarity: {similarity:.2f})")
                        visited.add(page_id)
                        pages_to_read.append(page_id)
                        # Record gap warning
                        knowledge_gaps.append(f"Orphaned page {page_id} added via safety net. Graph is missing a link.")
                        traversal_path.append({
                            "from": "vector_safety_net",
                            "to": page_id,
                            "link_type": "vector_fallback",
                            "condition_matched": f"similarity_{similarity:.2f}"
                        })
                        
        return pages_to_read, traversal_path, knowledge_gaps

    def save(self):
        """Saves adjacency lists to JSON."""
        if not self.adjacency_path:
            return
            
        os.makedirs(os.path.dirname(self.adjacency_path), exist_ok=True)
        with open(self.adjacency_path, 'w', encoding='utf-8') as f:
            json.dump(self.graph, f, indent=2)
            
    def load(self):
        """Loads adjacency lists from JSON."""
        if not self.adjacency_path or not os.path.exists(self.adjacency_path):
            return
            
        try:
            with open(self.adjacency_path, 'r', encoding='utf-8') as f:
                self.graph = json.load(f)
        except Exception as e:
            print(f"Error loading graph from {self.adjacency_path}: {e}")

if __name__ == '__main__':
    # Test graph traversal
    g = CortexGraph("test_adj.json")
    g.add_link("page_001", "page_002", "primary")
    g.add_link("page_001", "page_003", "secondary", "vip or discount")
    g.add_link("page_002", "page_004", "primary")
    
    pages, path, gaps = g.traverse(["page_001"], "Do we have a VIP discount?")
    print("Traversed pages:", pages)
    print("Path step count:", len(path))
    if os.path.exists("test_adj.json"):
        os.remove("test_adj.json")
