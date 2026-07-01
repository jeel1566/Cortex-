"""
Link discovery: propose page links for a new draft against approved pages.

Minimal approach:
1. Lexical match: find candidate pages by title/proposition overlap (no LLM).
2. For top candidates only, ask LLM to classify relationship type.
3. Return suggested_links list.

Link types: primary | related | conflict | duplicate
"""
import json
import os
from typing import Any, Dict, List, Optional

from app.llm.kimi import get_kimi_client

# ponytail: lexical match only unless candidates are ambiguous
_VALID_TYPES = {"primary", "related", "conflict", "duplicate"}


def _load_approved_pages(repo_dir: str) -> List[Dict[str, Any]]:
    """Load id/title/propositions from approved Git pages."""
    if not os.path.isdir(repo_dir):
        return []
    pages = []
    for fname in os.listdir(repo_dir):
        if not fname.endswith(".md"):
            continue
        page_id = fname[:-3]
        try:
            with open(os.path.join(repo_dir, fname), encoding="utf-8") as f:
                content = f.read()
            if not content.startswith("---"):
                continue
            from app.ingestion.validation import find_frontmatter_end
            end = find_frontmatter_end(content)
            if end == -1:
                continue
            try:
                import yaml
                meta = yaml.safe_load(content[3:end].strip()) or {}
            except Exception:
                meta = {}
            pages.append({
                "id": page_id,
                "title": meta.get("title", page_id),
                "propositions": [
                    p.get("text", "") if isinstance(p, dict) else str(p)
                    for p in (meta.get("propositions") or [])
                ],
            })
        except Exception:
            continue
    return pages


def _lexical_score(candidate: Dict, new_title: str, new_prop_texts: List[str]) -> float:
    """Simple overlap score: word Jaccard on title + proposition tokens."""
    def tokens(s: str):
        return set(s.lower().split())

    new_tokens = tokens(new_title) | {t for p in new_prop_texts for t in tokens(p)}
    cand_tokens = tokens(candidate["title"]) | {t for p in candidate["propositions"] for t in tokens(p)}
    if not new_tokens or not cand_tokens:
        return 0.0
    return len(new_tokens & cand_tokens) / len(new_tokens | cand_tokens)


def discover_links(
    tenant_id: str,
    new_draft_title: str,
    new_propositions: List[Dict],
    repo_dir: str,
    max_llm_candidates: int = 5,
) -> List[Dict[str, Any]]:
    """
    Returns a list of suggested link dicts matching the schema:
      {target_page_id, relationship_type, reason, evidence_segment_ids}

    Never returns links to pages that don't exist.
    """
    approved = _load_approved_pages(repo_dir)
    if not approved:
        return []

    new_prop_texts = [p.get("text", "") for p in new_propositions]

    # Score all candidates lexically
    scored = sorted(
        [(c, _lexical_score(c, new_draft_title, new_prop_texts)) for c in approved],
        key=lambda x: x[1],
        reverse=True,
    )
    # Only proceed with candidates above threshold
    candidates = [(c, score) for c, score in scored if score > 0.05][:max_llm_candidates]
    if not candidates:
        return []

    # Ask LLM to classify the top candidates
    try:
        client = get_kimi_client(tenant_id)

        prompt_candidates = [
            {"page_id": c["id"], "title": c["title"], "propositions": c["propositions"][:3]}
            for c, _ in candidates
        ]
        system = (
            "You are a knowledge graph editor. Given a new draft and candidate pages, "
            "classify the relationship. Output only a JSON array."
        )
        user = (
            f"New draft title: {new_draft_title}\n"
            f"New draft propositions (sample): {json.dumps(new_prop_texts[:5])}\n\n"
            f"Candidate pages: {json.dumps(prompt_candidates)}\n\n"
            "For each candidate that has a meaningful relationship, output a JSON array of objects:\n"
            '[{"target_page_id":"page_...","relationship_type":"primary|related|conflict|duplicate",'
            '"reason":"...","evidence_segment_ids":[]}]\n'
            "Only include candidates with a clear relationship. Output [] if none qualify.\n"
            "No markdown fences, no commentary."
        )
        raw = client.chat_completion(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.1,
            max_tokens=800,
        )
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        links = json.loads(text)
        if not isinstance(links, list):
            return []

        # Validate: only keep links to pages that actually exist
        existing_ids = {c["id"] for c, _ in candidates}
        result = []
        for lnk in links:
            pid = lnk.get("target_page_id", "")
            rt = lnk.get("relationship_type", "related")
            reason = lnk.get("reason", "")
            if pid in existing_ids and rt in _VALID_TYPES and reason:
                result.append({
                    "target_page_id": pid,
                    "relationship_type": rt,
                    "reason": reason,
                    "evidence_segment_ids": lnk.get("evidence_segment_ids", []),
                })
        return result

    except Exception:
        # LLM unavailable — return lexical-only suggestions
        return [
            {
                "target_page_id": c["id"],
                "relationship_type": "related",
                "reason": f"Lexical overlap score {score:.2f} with '{c['title']}'",
                "evidence_segment_ids": [],
            }
            for c, score in candidates[:3]
        ]
