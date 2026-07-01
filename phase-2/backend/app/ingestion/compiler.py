"""
DraftCompiler: LLM-backed synthesis of source segments into knowledge pages.

Flow:
  source_segments -> LLM prompt -> structured JSON -> validated Cortex markdown draft

If LLM is not configured or errors, stores a REJECTED draft with clear error.
Raw segments remain searchable regardless of LLM outcome.
"""
import json
import uuid
from typing import Any, Dict, List, Optional

from app.ingestion.engine_models import NormalizedSourceDocument, NormalizedSourceSegment
from app.llm.kimi import get_kimi_client

# ponytail: keep group_segments_by_heading — existing tests call it directly.
def _group_by_heading(segments: List[NormalizedSourceSegment]) -> Dict[str, List[NormalizedSourceSegment]]:
    grouped: Dict[str, List[NormalizedSourceSegment]] = {}
    for s in segments:
        key = " > ".join(s.heading_path) if s.heading_path else "General"
        grouped.setdefault(key, []).append(s)
    return grouped


_COMPILER_SYSTEM = """\
You are a knowledge compiler for Cortex Knowledge OS.
Your job is to synthesize raw source evidence into a structured knowledge page.
You must ONLY include claims that are directly supported by the provided evidence.
If evidence is insufficient for a claim, add it to knowledge_gaps — do not invent.
Output ONLY the JSON object below. No markdown fences, no preamble, no commentary.
"""

_COMPILER_USER_TMPL = """\
Evidence segments from source document "{title}":
{evidence_json}

Existing approved page catalog (for link suggestions, may be empty):
{catalog_json}

Produce a single JSON object matching this exact schema:
{{
  "title": "<concise knowledge page title>",
  "summary": "<2-3 sentence summary>",
  "sections": [
    {{
      "heading": "<section heading>",
      "body": "<section body>",
      "evidence_segment_ids": ["srcseg_..."]
    }}
  ],
  "propositions": [
    {{
      "text": "<precise factual claim>",
      "evidence_segment_ids": ["srcseg_..."],
      "source_quotes": ["<exact snippet from the evidence text>"],
      "confidence": 0.0,
      "sensitivity": "public|team|confidential|restricted"
    }}
  ],
  "suggested_links": [
    {{
      "target_page_id": "page_...",
      "relationship_type": "primary|related|conflict|duplicate",
      "reason": "<why>",
      "evidence_segment_ids": ["srcseg_..."]
    }}
  ],
  "knowledge_gaps": ["<gap description>"]
}}

Rules:
- Every proposition MUST have at least one evidence_segment_id from the list above.
- Every section MUST have evidence_segment_ids.
- source_quotes must be verbatim substrings of the evidence text.
- confidence must be between 0.0 and 1.0.
- Omit suggested_links if no catalog exists or no match is found.
- Do NOT include prompt text, "Expected Output", "Input JSON", or meta-commentary.
"""


def _build_evidence_items(segments: List[NormalizedSourceSegment], segment_db_rows: List[Dict]) -> List[Dict]:
    """Build evidence item list for the LLM prompt. Uses DB row IDs when available."""
    # Map content_hash -> db row id so we can use real srcseg_ IDs
    hash_to_id = {r["content_hash"]: r["id"] for r in segment_db_rows if r.get("content_hash") and r.get("id")}
    items = []
    for s in segments:
        seg_id = hash_to_id.get(s.content_hash, f"srcseg_{s.content_hash[:12]}")
        items.append({
            "evidence_segment_id": seg_id,
            "heading_path": " > ".join(s.heading_path) if s.heading_path else "",
            "segment_type": s.segment_type,
            "text": s.text[:800],  # cap per-segment to keep prompt size bounded
            "position": s.position,
        })
    return items


def _parse_llm_json(raw: str) -> Dict:
    """Strip markdown fences then parse JSON."""
    text = raw.strip()
    if text.startswith("```"):
        # strip opening fence line and closing fence
        lines = text.splitlines()
        # drop first line (```json or ```) and last line (```)
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    return json.loads(text)


def _build_draft_markdown(
    draft_id: str,
    source_external_id: str,
    llm_data: Dict,
    segment_db_rows: List[Dict],
) -> str:
    """Convert LLM JSON output to Cortex canonical markdown."""
    title = llm_data.get("title", "Untitled")
    summary = llm_data.get("summary", "")
    sections = llm_data.get("sections", [])
    propositions = llm_data.get("propositions", [])
    suggested_links = llm_data.get("suggested_links", [])
    knowledge_gaps = llm_data.get("knowledge_gaps", [])

    # Build primary/related/conflict/duplicate link lists
    primary_links, related_links, conflict_links, duplicate_links = [], [], [], []
    for lnk in suggested_links:
        rt = lnk.get("relationship_type", "related")
        entry = lnk.get("target_page_id", "")
        if rt == "primary":
            primary_links.append(entry)
        elif rt == "conflict":
            conflict_links.append(entry)
        elif rt == "duplicate":
            duplicate_links.append(entry)
        else:
            related_links.append(entry)

    # Propositions YAML block
    prop_lines = []
    for idx, p in enumerate(propositions):
        prop_id = f"prop_{uuid.uuid4().hex[:8]}"
        p["id"] = prop_id  # mutate in-place so caller can persist
        ev_ids = p.get("evidence_segment_ids", [])
        quotes = p.get("source_quotes", [])
        confidence = p.get("confidence", 0.85)
        sensitivity = p.get("sensitivity", "team")
        ev_yaml = "".join(f'\n      - "{e}"' for e in ev_ids)
        quote_yaml = "".join(f'\n      - "{q.replace(chr(34), chr(39))}"' for q in quotes)
        prop_lines.append(
            f'  - id: "{prop_id}"\n'
            f'    text: "{p["text"].replace(chr(34), chr(39))}"\n'
            f"    evidence_segment_ids:{ev_yaml or chr(10) + '      []'}\n"
            f"    source_quotes:{quote_yaml or chr(10) + '      []'}\n"
            f"    confidence: {confidence}\n"
            f"    sensitivity: \"{sensitivity}\""
        )
    props_yaml = "\n".join(prop_lines) if prop_lines else "  []"

    # Link lists YAML
    def _yaml_list(items: List[str], indent: int = 2) -> str:
        if not items:
            return " []"
        pad = " " * indent
        return "\n" + "".join(f'{pad}- "{i}"\n' for i in items).rstrip()

    # Knowledge gaps YAML
    gaps_yaml = _yaml_list(knowledge_gaps)
    sources_yaml = f'  - "{source_external_id}"'

    frontmatter = (
        "---\n"
        f'id: "{draft_id}"\n'
        f'title: "{title.replace(chr(34), chr(39))}"\n'
        f"sources:\n{sources_yaml}\n"
        f"propositions:\n{props_yaml}\n"
        f"primary_links:{_yaml_list(primary_links)}\n"
        f"related_links:{_yaml_list(related_links)}\n"
        f"conflict_links:{_yaml_list(conflict_links)}\n"
        f"duplicate_links:{_yaml_list(duplicate_links)}\n"
        f"knowledge_gaps:{gaps_yaml}\n"
        "synthesis_validation:\n"
        "  proposition_coverage: 0.0\n"
        "  hallucination_rate: 0.0\n"
        "  completeness_score: 0\n"
        "  validation_passed: false\n"
        "---\n"
    )

    # Body
    body_parts = [f"# {title}\n", f"## Summary\n{summary}\n"]

    if sections:
        body_parts.append("## Sections")
        for sec in sections:
            body_parts.append(f"### {sec.get('heading', 'Section')}\n{sec.get('body', '')}")

    if propositions:
        body_parts.append("## Propositions")
        for p in propositions:
            ev_ids = ", ".join(p.get("evidence_segment_ids", []))
            body_parts.append(f"- {p['text']} *(evidence: {ev_ids})*")

    if knowledge_gaps:
        body_parts.append("## Knowledge Gaps")
        for g in knowledge_gaps:
            body_parts.append(f"- {g}")

    return frontmatter + "\n" + "\n\n".join(body_parts) + "\n"


def _rejected_draft_content(draft_id: str, source_external_id: str, error: str) -> str:
    """Minimal valid-structure rejected draft — no invented content."""
    return (
        "---\n"
        f'id: "{draft_id}"\n'
        f'title: "Compilation Failed"\n'
        f"sources:\n  - \"{source_external_id}\"\n"
        "propositions: []\n"
        "primary_links: []\n"
        "related_links: []\n"
        "conflict_links: []\n"
        "duplicate_links: []\n"
        "knowledge_gaps:\n"
        f'  - "LLM compilation failed: {error[:200]}"\n'
        "synthesis_validation:\n"
        "  proposition_coverage: 0.0\n"
        "  hallucination_rate: 0.0\n"
        "  completeness_score: 0\n"
        "  validation_passed: false\n"
        "---\n\n"
        "# Compilation Failed\n\n"
        f"LLM compilation failed. Raw source segments remain searchable.\n\nError: {error}\n"
    )


class DraftCompiler:
    # ponytail: kept for existing tests that call this directly
    def group_segments_by_heading(self, segments):
        return _group_by_heading(segments)

    def compile_draft(
        self,
        tenant_id: str,
        document: NormalizedSourceDocument,
        segments: List[NormalizedSourceSegment],
        segment_db_rows: Optional[List[Dict]] = None,
        approved_page_catalog: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Compile a knowledge page draft using the LLM.

        Returns dict with keys: draft_id, title, content, validation_passed,
        errors, propositions (list of dicts with full rich fields).

        On LLM failure: returns validation_passed=False, status='REJECTED',
        propositions=[], content=rejected stub. Never returns fake synthesized content.
        """
        from app.ingestion.validation import verify_page_shape

        draft_id = f"draft_{document.content_hash[:12]}"
        segment_db_rows = segment_db_rows or []
        approved_page_catalog = approved_page_catalog or []

        evidence_items = _build_evidence_items(segments, segment_db_rows)

        try:
            client = get_kimi_client(tenant_id)

            catalog_json = json.dumps(
                [{"id": p.get("id"), "title": p.get("title")} for p in approved_page_catalog],
                ensure_ascii=False,
            )
            user_msg = _COMPILER_USER_TMPL.format(
                title=document.title,
                evidence_json=json.dumps(evidence_items, ensure_ascii=False, indent=2),
                catalog_json=catalog_json if catalog_json != "[]" else "[]",
            )

            raw = client.chat_completion(
                [
                    {"role": "system", "content": _COMPILER_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.2,
                max_tokens=3000,
            )

            llm_data = _parse_llm_json(raw)

        except Exception as exc:
            error_msg = str(exc)
            content = _rejected_draft_content(draft_id, document.source_object_external_id, error_msg)
            return {
                "draft_id": draft_id,
                "title": document.title,
                "content": content,
                "validation_passed": False,
                "status": "REJECTED",
                "errors": [f"LLM compilation failed: {error_msg}"],
                "propositions": [],
            }

        content = _build_draft_markdown(
            draft_id,
            document.source_object_external_id,
            llm_data,
            segment_db_rows,
        )

        validation_passed = True
        errors = []

        try:
            # ponytail: compile-time checks structural + leakage only.
            # Strict evidence ID cross-check happens at approval via verify_page_shape(allowed_segment_ids=...).
            verify_page_shape(
                content,
                allowed_segment_ids=None,
                strict_evidence=bool(llm_data.get("propositions")),
            )
        except ValueError as exc:
            validation_passed = False
            errors.append(str(exc))

        # Extract rich propositions with all fields for DB persistence
        rich_props = []
        for p in llm_data.get("propositions", []):
            rich_props.append({
                "id": p.get("id", f"prop_{uuid.uuid4().hex[:8]}"),
                "text": p.get("text", ""),
                "evidence_segment_ids": p.get("evidence_segment_ids", []),
                "source_quotes": p.get("source_quotes", []),
                "confidence": float(p.get("confidence", 0.85)),
                "sensitivity": p.get("sensitivity", "team"),
            })

        return {
            "draft_id": draft_id,
            "title": llm_data.get("title", document.title),
            "content": content,
            "validation_passed": validation_passed,
            "status": "DRAFT" if validation_passed else "REJECTED",
            "errors": errors,
            "propositions": rich_props,
        }
