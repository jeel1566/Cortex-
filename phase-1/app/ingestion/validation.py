import os
import sys
import json
import datetime
from typing import List, Dict, Any

# Add parent directories to sys.path
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

def validate_page(sources: List[str], synthesized_page: str) -> Dict[str, Any]:
    """
    Validates a synthesized page against its raw source sentences using Kimi K2.5.
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
        
    client = get_kimi_client()
    
    messages = [
        {"role": "system", "content": VALIDATION_PROMPT},
        {"role": "user", "content": f"Sources:\n{json.dumps(sources)}\n\nSynthesized Page:\n{synthesized_page}"}
    ]
    
    raw_response = None
    clean_text = None
    try:
        raw_response = client.chat_completion(messages, temperature=0.1, max_tokens=512)
        
        # Clean JSON wrappers and extract JSON content
        clean_text = raw_response.strip()
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0].strip()
        else:
            # For validation, we expect a JSON object. Find the main object block.
            start_idx = clean_text.find('{')
            if start_idx != -1:
                end_idx = clean_text.rfind('}')
                if end_idx != -1 and start_idx < end_idx:
                    clean_text = clean_text[start_idx:end_idx+1]
            
        data = json.loads(clean_text)
        return data
    except Exception as e:
        print(f"Validation API error: {e}")
        print(f"[DEBUG] raw_response:\n{raw_response}")
        print(f"[DEBUG] clean_text:\n{clean_text}")
        # Default safety fallback (fails validation so page goes to draft)
        return {
            "proposition_coverage": 0.5,
            "hallucination_rate": 0.1,
            "completeness_score": 5,
            "validation_passed": False,
            "reason": f"Fallback triggered due to verification error: {e}"
        }

if __name__ == '__main__':
    # Simple test stub run
    test_sources = [
        "Max started the Superset project in 2015 while at Airbnb.",
        "Erik is a full stack engineer at Airbnb and a PMC member for Superset."
    ]
    test_page = """---
id: page_001
title: Superset History and Airbnb PMC
version: 1
last_updated: 2026-05-30
access_level: team
sources:
  - slack://C1/123
---
# Superset History

Max created Superset back in 2015 when he was working at Airbnb [^1]. Erik is also based at Airbnb as a full stack engineer and serves on the PMC board [^2].
"""
    try:
        res = validate_page(test_sources, test_page)
        print("Validation Result:", res)
    except Exception as e:
        print("Expected mock failure:", e)
