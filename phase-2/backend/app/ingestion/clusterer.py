import os
import sys
import numpy as np
from typing import List, Dict, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.llm.embedding import encode_batch

def cluster_sentences(classified_sentences: List[Dict[str, Any]], similarity_threshold: float = 0.65) -> List[List[Dict[str, Any]]]:
    """
    Groups a list of classified sentences into semantic clusters (decision units).
    """
    if not classified_sentences:
        return []
        
    texts = [item["text"] for item in classified_sentences]
    embeddings = np.array(encode_batch(texts))
    
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized_embeddings = embeddings / norms
    
    similarity_matrix = np.dot(normalized_embeddings, normalized_embeddings.T)
    
    visited = set()
    clusters = []
    
    for i in range(len(classified_sentences)):
        if i in visited:
            continue
            
        similar_indices = np.where(similarity_matrix[i] >= similarity_threshold)[0]
        
        cluster = []
        for idx in similar_indices:
            if idx not in visited:
                visited.add(idx)
                cluster.append(classified_sentences[idx])
                
        if cluster:
            clusters.append(cluster)
            
    return clusters
