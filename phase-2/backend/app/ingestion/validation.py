import os
import sys
import json
from typing import List, Dict, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

VALIDATION_PROMPT = """You are a meticulous Quality Assurance evaluator. Your task is to validate a synthesized knowledge page against its raw source sentences.

<checks>
1. Proposition Coverage:
   - Extract key factual claims from the source sentences.
   - Verify if each claim is correctly captured in the synthesized page.
   - Calculate coverage: (claims found in page) / (total source claims) [0.0 - 1.0].
2. Hallucination Rate:
   - Verify if every claim made in the page is traceable to and supported by the source sentences.
   - Calculate rate: (unverifiable claims) / (total page claims) [0.0 - 1.0].
3. Completeness Score:
   - Evaluate if the page is a comprehensive, cohesive summary of the raw sources.
   - Score: [1 - 10] integer.
</checks>

<criteria>
Validation passes only if:
- Proposition Coverage >= 0.90
- Hallucination Rate <= 0.02
- Completeness Score >= 7
</criteria>

<instructions>
- Output MUST be a single valid JSON object containing exactly the keys: "proposition_coverage" (float), "hallucination_rate" (float), "completeness_score" (int), "validation_passed" (bool), and "reason" (str).
- Do not output any markdown code blocks, greeting, or conversational text. Start directly with '{' and end with '}'.
</instructions>"""

def validate_page(sources: List[str], synthesized_page: str, tenant_id: str = None) -> Dict[str, Any]:
    """
    Validates a synthesized page against its raw source sentences using Kimi.
    Returns a dictionary with scores and status.
    """
    if not sources or not synthesized_page:
        return {
            "proposition_coverage": 0.0,
            "hallucination_rate": 1.0,
            "completeness_score": 1,
            "validation_passed": False,
            "reason": "Missing sources or page content."
        }
        
    from app.llm.kimi import get_kimi_client

    client = get_kimi_client(tenant_id)
    
    messages = [
        {"role": "system", "content": VALIDATION_PROMPT},
        {"role": "user", "content": f"Sources:\n{json.dumps(sources)}\n\nSynthesized Page:\n{synthesized_page}"}
    ]
    
    try:
        raw_response = client.chat_completion(messages, temperature=0.1)
        clean_text = raw_response.strip()
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0].strip()
            
        data = json.loads(clean_text)
        return data
    except Exception as e:
        print(f"Validation API error: {e}")
        return {
            "proposition_coverage": 0.5,
            "hallucination_rate": 0.1,
            "completeness_score": 5,
            "validation_passed": False,
            "reason": f"Fallback triggered due to verification error: {e}"
        }

def find_frontmatter_end(content: str) -> int:
    """
    Finds the closing separator index of the YAML frontmatter robustly.
    It splits content by line and returns the exact character offset of the
    first line starting from line 1 that is exactly '---' after stripping.
    Returns -1 if not found.
    """
    if not content.startswith("---"):
        return -1
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return -1
    current_offset = len(lines[0])
    for line in lines[1:]:
        if line.strip() == "---":
            return current_offset
        current_offset += len(line)
    return -1

def verify_page_shape(content: str, allowed_segment_ids: List[str] = None, strict_evidence: bool = True) -> bool:
    """
    Validates that the generated knowledge page strictly conforms to the expected shape:
    - Must start with '---'
    - Must have a closing '---'
    - YAML frontmatter must parse and contain id, title, sources, propositions, and synthesis_validation
    - Must not contain prompt-leak substrings like 'Expected Output', 'Input JSON', '</output_format>'
    - Must not be wrapped in markdown code fences as a whole
    - If strict_evidence is True, every proposition must have non-empty evidence_segment_ids
    - If allowed_segment_ids is provided, evidence_segment_ids must be within it
    """
    if not content:
        raise ValueError("Page content is empty.")

    # 1. Check markdown fence wrapping entire page
    stripped_content = content.strip()
    if (stripped_content.startswith("```markdown") or stripped_content.startswith("```")) and stripped_content.endswith("```"):
        raise ValueError("Page content is wrapped in outer markdown code fences.")

    # 2. Check prompt leakage blacklist
    blacklist = [
        "expected output",
        "input json",
        "</output_format>",
        "based on the provided",
        "assistant commentary",
        "assistant response",
    ]
    content_lower = content.lower()
    for word in blacklist:
        if word in content_lower:
            raise ValueError(f"Page contains prompt leakage or assistant meta-text: '{word}'")

    # 3. Check YAML frontmatter boundaries (strict starting constraint)
    if not content.startswith("---"):
        raise ValueError("Page does not start with YAML frontmatter separator '---'")

    close_idx = find_frontmatter_end(content)
    if close_idx == -1:
        raise ValueError("Page lacks a closing YAML frontmatter separator '---'")

    yaml_text = content[3:close_idx].strip()
    
    # 4. Parse YAML
    try:
        try:
            import yaml
            data = yaml.safe_load(yaml_text)
        except Exception:
            data = _parse_frontmatter_keys(yaml_text)
    except Exception as e:
        raise ValueError(f"Failed to parse YAML frontmatter: {e}")

    if not isinstance(data, dict):
        raise ValueError("YAML frontmatter is not a valid dictionary structure.")

    # 5. Check required keys
    required_keys = ["id", "title", "sources", "propositions", "synthesis_validation"]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"YAML frontmatter is missing required key: '{key}'")

    # 6. Check propositions evidence segment IDs
    props = data.get("propositions", [])
    if not isinstance(props, list):
        raise ValueError("propositions must be a list in frontmatter.")
        
    for idx, p in enumerate(props):
        if strict_evidence:
            if not isinstance(p, dict):
                raise ValueError(f"Proposition at index {idx} must be a dictionary with evidence_segment_ids.")
            if "evidence_segment_ids" not in p or not p["evidence_segment_ids"]:
                raise ValueError(f"Proposition at index {idx} lacks evidence_segment_ids.")
            if not isinstance(p["evidence_segment_ids"], list):
                raise ValueError(f"evidence_segment_ids for proposition at index {idx} must be a list.")
            if allowed_segment_ids is not None:
                for ev_id in p["evidence_segment_ids"]:
                    if ev_id not in allowed_segment_ids:
                        raise ValueError(f"Proposition evidence ID '{ev_id}' does not exist in source segments.")
        else:
            # If not strict, we still check allowed_segment_ids if the dictionary has them
            if isinstance(p, dict) and "evidence_segment_ids" in p and isinstance(p["evidence_segment_ids"], list):
                if allowed_segment_ids is not None:
                    for ev_id in p["evidence_segment_ids"]:
                        if ev_id not in allowed_segment_ids:
                            raise ValueError(f"Proposition evidence ID '{ev_id}' does not exist in source segments.")

    return True


def validate_compiled_draft(
    content: str,
    propositions: list,
    allowed_segment_ids: List[str] = None,
    approved_page_ids: List[str] = None,
) -> Dict[str, Any]:
    """
    Extended validation for LLM-compiled drafts.
    Returns {validation_passed, errors, warnings, validated_at}.
    Checks verify_page_shape PLUS:
    - confidence in [0.0, 1.0]
    - sensitivity must be one of public|team|confidential|restricted
    - source_quotes non-empty (warning if missing, not error)
    - suggested link targets must be in approved_page_ids if provided
    """
    from app.ingestion.engine_models import utc_now
    errors: List[str] = []
    warnings: List[str] = []
    valid_sensitivities = {"public", "team", "confidential", "restricted"}

    try:
        verify_page_shape(content, allowed_segment_ids=allowed_segment_ids, strict_evidence=bool(propositions))
    except ValueError as exc:
        errors.append(str(exc))

    for idx, p in enumerate(propositions):
        text = p.get("text", "").strip()
        if not text:
            errors.append(f"Proposition {idx}: empty text")
        ev_ids = p.get("evidence_segment_ids", [])
        if not ev_ids:
            errors.append(f"Proposition {idx}: missing evidence_segment_ids")
        conf = p.get("confidence")
        if conf is not None:
            try:
                c = float(conf)
                if not (0.0 <= c <= 1.0):
                    errors.append(f"Proposition {idx}: confidence {c} outside [0.0, 1.0]")
            except (TypeError, ValueError):
                errors.append(f"Proposition {idx}: confidence must be numeric")
        sens = p.get("sensitivity", "team")
        if sens not in valid_sensitivities:
            errors.append(f"Proposition {idx}: invalid sensitivity '{sens}'")
        quotes = p.get("source_quotes", [])
        if not quotes:
            warnings.append(f"Proposition {idx}: no source_quotes provided")

    if approved_page_ids is not None:
        approved_set = set(approved_page_ids)
        # parse suggested_links from content frontmatter
        try:
            import yaml
            fm_end = find_frontmatter_end(content)
            if fm_end != -1:
                meta = yaml.safe_load(content[3:fm_end].strip()) or {}
                for link_type in ("primary_links", "related_links", "conflict_links", "duplicate_links"):
                    for pid in (meta.get(link_type) or []):
                        if pid and pid not in approved_set:
                            errors.append(f"Link target '{pid}' in {link_type} does not exist in approved pages")
        except Exception:
            pass

    passed = not errors
    return {
        "validation_passed": passed,
        "errors": errors,
        "warnings": warnings,
        "validated_at": utc_now(),
    }


def _parse_frontmatter_keys(yaml_text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    current_key = None
    for raw_line in yaml_text.splitlines():
        if not raw_line.strip():
            continue
        if not raw_line.startswith(" ") and ":" in raw_line:
            key, value = raw_line.split(":", 1)
            current_key = key.strip()
            value = value.strip()
            data[current_key] = [] if value == "" else value.strip('"').strip("'")
            continue
        if current_key and raw_line.strip().startswith("- "):
            if not isinstance(data.get(current_key), list):
                data[current_key] = []
            data[current_key].append(raw_line.strip()[2:].strip('"').strip("'"))
            continue
        if current_key and ":" in raw_line:
            if not isinstance(data.get(current_key), dict):
                data[current_key] = {}
            key, value = raw_line.strip().split(":", 1)
            data[current_key][key.strip()] = value.strip()
    return data
            

