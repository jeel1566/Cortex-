import os
from typing import List
from fastembed import TextEmbedding

_model = None

def get_embedding_model() -> TextEmbedding:
    global _model
    if _model is None:
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
    embeddings = list(model.embed(texts))
    return [[float(x) for x in emb] for emb in embeddings]
