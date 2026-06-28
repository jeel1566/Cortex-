import json
import os
import sys
from typing import List, Dict, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.llm.kimi import get_kimi_client

CLASSIFIER_PROMPT = """You are a highly precise Natural Language Processing classifier. Your goal is to classify raw log sentences into one of 5 distinct speech-act categories.

# speech-act categories
- CONDITION: Context, timing, triggers, or pre-requisite rules. (e.g. "if", "when", "in case", "upon X")
- PRESCRIPTION: Mandatory policies, requirements, bounds, or specific recommendations. (e.g. "Refunds must be requested within 30 days", "should use Python 3.11")
- PROCEDURE: Sequence of steps or operational commands. (e.g. "step 1", "next, run git push", "then click the login button")
- EXCEPTION: Overrides, exclusions, or error cases. (e.g. "except for managers", "unless X is set to false")
- OUTCOME: Result, response, consequence, or side effect. (e.g. "which generates a 500 error", "to create the user profile")

<instructions>
1. Input format: A JSON array of sentence objects, each with "id" (int) and "text" (str).
2. Output format: You MUST respond ONLY with a valid JSON array of objects, containing exactly "id" (int) and "type" (one of the 5 uppercase strings: CONDITION, PRESCRIPTION, PROCEDURE, EXCEPTION, OUTCOME).
3. Do not output any markdown code blocks, text wrapper, greeting, or extra conversational text.
</instructions>

Example Input:
[
  {"id": 0, "text": "If a customer requests a refund after 60 days"},
  {"id": 1, "text": "we must reject the request"}
]

Example Output:
[
  {"id": 0, "type": "CONDITION"},
  {"id": 1, "type": "PRESCRIPTION"}
]"""

CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "phase-1", "data", "classifier_cache.json")

def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_cache(cache: dict):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass

def classify_sentences(sentences: List[str], tenant_id: str = None) -> List[str]:
    """
    Classifies a list of sentences into speech-act types.
    Returns a list of uppercase strings representing the type of each sentence in order.
    """
    if not sentences:
        return []
        
    cache = load_cache()
    
    # Determine which sentences are missing from the cache
    missing_indices = []
    missing_texts = []
    results = [None] * len(sentences)
    
    for idx, text in enumerate(sentences):
        if text in cache:
            results[idx] = cache[text]
        else:
            missing_indices.append(idx)
            missing_texts.append(text)
            
    if missing_texts:
        client = get_kimi_client(tenant_id)
        input_data = [{"id": i, "text": txt} for i, txt in enumerate(missing_texts)]
        
        messages = [
            {"role": "system", "content": CLASSIFIER_PROMPT},
            {"role": "user", "content": json.dumps(input_data)}
        ]
        
        try:
            import time
            time.sleep(25)
            raw_response = client.chat_completion(messages, temperature=0.1, max_tokens=4096)
            clean_text = raw_response.strip()
            if "```json" in clean_text:
                clean_text = clean_text.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_text:
                clean_text = clean_text.split("```")[1].split("```")[0].strip()
                
            data = json.loads(clean_text)
            type_map = {item["id"]: item["type"] for item in data if "id" in item and "type" in item}
            
            # Save new results to cache and update results list
            for i, txt in enumerate(missing_texts):
                t = type_map.get(i, "OUTCOME")
                if t not in ["CONDITION", "PRESCRIPTION", "PROCEDURE", "EXCEPTION", "OUTCOME"]:
                    t = "OUTCOME"
                cache[txt] = t
                results[missing_indices[i]] = t
                
            save_cache(cache)
            
        except Exception as e:
            print(f"Classifier error: {e}. Falling back to default 'PRESCRIPTION' for missing sentences.")
            for i in range(len(missing_texts)):
                results[missing_indices[i]] = "PRESCRIPTION"
                
    return results
