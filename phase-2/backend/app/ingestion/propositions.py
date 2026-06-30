from typing import List, Dict, Any

def extract_propositions_from_segments(segments: List[Any]) -> List[Dict[str, Any]]:
    """
    Extracts factual claims (propositions) from the given segments.
    Each proposition is linked to the source segment ID/hash as evidence.
    """
    propositions = []
    for s in segments:
        if hasattr(s, "model_dump"):
            text = s.text
            content_hash = s.content_hash
            position = s.position
            # For pydantic models, check metadata for ID or use content_hash / position
            seg_id = s.metadata.get("id") if s.metadata else None
            if not seg_id:
                seg_id = content_hash or f"pos_{position}"
        else:
            text = s.get("text", "")
            content_hash = s.get("content_hash", "")
            position = s.get("position", 0)
            seg_id = s.get("id") or s.get("metadata", {}).get("id") or content_hash or f"pos_{position}"

        # Split text into sentences for sentence-level proposition mapping
        sentences = [sentence.strip() for sentence in text.replace("?", ".").replace("!", ".").split(".") if sentence.strip()]
        for sentence in sentences:
            if len(sentence) > 5:
                propositions.append({
                    "text": sentence,
                    "evidence_segment_ids": [seg_id],
                    "sensitivity": "team"
                })
    return propositions
