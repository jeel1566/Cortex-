import os
import sys
import json
from typing import List, Dict, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.llm.kimi import get_kimi_client

VALIDATION_PROMPT = """
You are an expert quality assurance evaluator for a Knowledge OS.
Your task is to validate a synthesized knowledge page against its raw source sentences.

Input:
1. Sources: A JSON list of sentences that were used to create the page.
2. Synthesized Page: The markdown page content (including the YAML header).

You MUST perform three checks:
Check 1: Proposition Coverage
- Extract the key factual claims from the source sentences.
- Check if each claim is correctly captured/reflected in the synthesized page.
- Calculate score as (claims found in page) / (total source claims). (Float between 0.0 and 1.0).

Check 2: Hallucination Rate
- Extract the claims made in the synthesized page.
- Check if each page claim can be traced back and verified by the source sentences.
- Calculate rate as (unverifiable claims) / (total page claims). (Float between 0.0 and 1.0).

Check 3: Completeness Score
- Evaluate if the page provides a complete, cohesive summary of the topic discussed in the sources.
- Rate the completeness on an integer scale of 1 to 10.

Validation Passed criteria:
- Proposition Coverage must be >= 0.90
- Hallucination Rate must be <= 0.02 (2%)
- Completeness Score must be >= 7

Output format: You MUST return a single JSON object containing exactly these fields:
- "proposition_coverage" (float between 0.0 and 1.0)
- "hallucination_rate" (float between 0.0 and 1.0)
- "completeness_score" (integer between 1 and 10)
- "validation_passed" (boolean)
- "reason" (string explaining your scoring)

Return ONLY valid JSON. No conversational text.
"""

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
