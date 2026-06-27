import os
from typing import List
from fastembed import TextEmbedding

_model = None

def get_embedding_model() -> TextEmbedding:
    global _model
    if _model is None:
        # BAAI/bge-small-en-v1.5 is optimized for CPU inference via ONNX Runtime
        _model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _model

def encode(text: str) -> List[float]:
    model = get_embedding_model()
    embeddings = list(model.embed([text]))
    return [float(x) for x in embeddings[0]]

def encode_batch(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    model = get_embedding_model()
    results = []
    chunk_size = 16
    for i in range(0, len(texts), chunk_size):
        chunk = texts[i:i+chunk_size]
        embeddings = list(model.embed(chunk))
        results.extend([[float(x) for x in emb] for emb in embeddings])
    return results

if __name__ == '__main__':
    print("Loading model and testing encoding...")
    v = encode("hello world")
    print(f"Vector dimensions: {len(v)}")
    print(f"Vector preview: {v[:5]}")
