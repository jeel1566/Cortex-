import os
import sys
import numpy as np
from typing import List, Dict, Any

# Add parent directories to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.llm.embedding import encode_batch

def cluster_sentences(classified_sentences: List[Dict[str, Any]], similarity_threshold: float = 0.65) -> List[List[Dict[str, Any]]]:
    """
    Groups a list of classified sentences into semantic clusters (decision units).
    
    classified_sentences is a list of dicts:
    [
        {"text": "If a customer requests a refund...", "type": "CONDITION", "metadata": {...}},
        ...
    ]
    
    Returns a list of clusters, where each cluster is a list of sentence dicts.
    """
    if not classified_sentences:
        return []
        
    texts = [item["text"] for item in classified_sentences]
    
    # 1. Generate embeddings locally
    embeddings = np.array(encode_batch(texts))
    
    # 2. Normalize embeddings for cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized_embeddings = embeddings / norms
    
    # 3. Compute cosine similarity matrix (dot product of normalized vectors)
    similarity_matrix = np.dot(normalized_embeddings, normalized_embeddings.T)
    
    # 4. Perform threshold-based clustering (single-pass grouping)
    visited = set()
    clusters = []
    
    for i in range(len(classified_sentences)):
        if i in visited:
            continue
            
        # Find all indices of sentences that are semantically close to sentence i
        similar_indices = np.where(similarity_matrix[i] >= similarity_threshold)[0]
        
        cluster = []
        for idx in similar_indices:
            if idx not in visited:
                visited.add(idx)
                cluster.append(classified_sentences[idx])
                
        if cluster:
            clusters.append(cluster)
            
    return clusters

if __name__ == '__main__':
    # Simple test run
    test_data = [
        {"text": "Refunds are processed within 5 days", "type": "PRESCRIPTION"},
        {"text": "We issue standard refunds in under 5 business days", "type": "PRESCRIPTION"},
        {"text": "To compile the binary run go build", "type": "PROCEDURE"},
        {"text": "The compile step requires the Go compiler", "type": "CONDITION"}
    ]
    cls = cluster_sentences(test_data)
    print(f"Grouped into {len(cls)} clusters:")
    for i, cluster in enumerate(cls):
        print(f"Cluster {i+1}: {[item['text'] for item in cluster]}")
