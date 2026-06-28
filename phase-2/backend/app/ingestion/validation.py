import os
import sys
import json
from typing import List, Dict, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.llm.kimi import get_kimi_client

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

def verify_page_shape(content: str) -> bool:
    """
    Validates that the generated knowledge page strictly conforms to the expected shape:
    - Must start with '---'
    - Must have a closing '---'
    - YAML frontmatter must parse and contain id, title, sources, propositions, and synthesis_validation
    - Must not contain prompt-leak substrings like 'Expected Output', 'Input JSON', '</output_format>'
    """
    if not content:
        raise ValueError("Page content is empty.")

    # 1. Check prompt leakage blacklist
    blacklist = [
        "expected output",
        "input json",
        "</output_format>",
        "based on the provided source data"
    ]
    content_lower = content.lower()
    for word in blacklist:
        if word in content_lower:
            raise ValueError(f"Page contains prompt leakage or assistant meta-text: '{word}'")

    # 2. Check YAML frontmatter boundaries
    if not content.startswith("---"):
        raise ValueError("Page does not start with YAML frontmatter separator '---'")

    close_idx = content.find("---", 3)
    if close_idx == -1:
        raise ValueError("Page lacks a closing YAML frontmatter separator '---'")

    import yaml
    yaml_text = content[3:close_idx].strip()
    
    # 3. Parse YAML
    try:
        data = yaml.safe_load(yaml_text)
    except Exception as e:
        raise ValueError(f"Failed to parse YAML frontmatter: {e}")

    if not isinstance(data, dict):
        raise ValueError("YAML frontmatter is not a valid dictionary structure.")

    # 4. Check required keys
    required_keys = ["id", "title", "sources", "propositions", "synthesis_validation"]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"YAML frontmatter is missing required key: '{key}'")

    return True
            

