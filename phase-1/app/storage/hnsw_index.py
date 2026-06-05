import os
import json
import numpy as np
from typing import List, Dict, Any, Tuple

class NumPyVectorIndex:
    """
    NumPy-based Vector Index used as a compile-free, high-performance alternative to hnswlib.
    Designed to calculate cosine similarity via NumPy matrix multiplication.
    """
    def __init__(self, index_path: str = None, dim: int = 384):
        self.index_path = index_path
        self.dim = dim
        self.page_ids = []
        self.embeddings = []  # List of List[float]
        
        if index_path and os.path.exists(index_path):
            self.load()
            
    def add_page(self, page_id: str, embedding: List[float]):
        """Adds or updates a page embedding in the index."""
        if len(embedding) != self.dim:
            raise ValueError(f"Embedding dimension mismatch. Expected {self.dim}, got {len(embedding)}")
            
        if page_id in self.page_ids:
            idx = self.page_ids.index(page_id)
            self.embeddings[idx] = embedding
        else:
            self.page_ids.append(page_id)
            self.embeddings.append(embedding)
            
    def search(self, query_vector: List[float], k: int = 3) -> List[Tuple[str, float]]:
        """Searches the index and returns the top-k (page_id, similarity) tuples."""
        if not self.embeddings:
            return []
            
        # Convert to numpy arrays
        query = np.array(query_vector)
        matrix = np.array(self.embeddings)
        
        # Calculate L2 norms
        query_norm = np.linalg.norm(query)
        matrix_norms = np.linalg.norm(matrix, axis=1)
        
        # Avoid division by zero
        if query_norm == 0:
            query_norm = 1.0
        matrix_norms[matrix_norms == 0] = 1.0
        
        # Calculate cosine similarity: A . B / (|A| * |B|)
        dot_products = np.dot(matrix, query)
        similarities = dot_products / (matrix_norms * query_norm)
        
        # Sort indices in descending order of similarity
        top_k_indices = np.argsort(similarities)[::-1][:k]
        
        results = []
        for idx in top_k_indices:
            results.append((self.page_ids[idx], float(similarities[idx])))
        return results
        
    def save(self):
        """Saves the vector index data to a JSON file."""
        if not self.index_path:
            return
            
        # Ensure parent directories exist
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        
        data = {
            "page_ids": self.page_ids,
            "embeddings": self.embeddings,
            "dim": self.dim
        }
        with open(self.index_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
            
    def load(self):
        """Loads the vector index data from a JSON file."""
        if not self.index_path or not os.path.exists(self.index_path):
            return
            
        try:
            with open(self.index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.page_ids = data.get("page_ids", [])
                self.embeddings = data.get("embeddings", [])
                self.dim = data.get("dim", 384)
        except Exception as e:
            print(f"Error loading index from {self.index_path}: {e}")

if __name__ == '__main__':
    # Test index functionality
    idx_file = "test_index.json"
    idx = NumPyVectorIndex(idx_file, dim=3)
    idx.add_page("page_001", [1.0, 0.0, 0.0])
    idx.add_page("page_002", [0.0, 1.0, 0.0])
    idx.add_page("page_003", [0.8, 0.6, 0.0])
    
    res = idx.search([0.9, 0.1, 0.0], k=2)
    print("Search results (expected page_003, page_001):", res)
    idx.save()
    
    # Reload and test
    idx2 = NumPyVectorIndex(idx_file, dim=3)
    print("Reloaded page_ids:", idx2.page_ids)
    if os.path.exists(idx_file):
        os.remove(idx_file)
