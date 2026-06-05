import json
import os
import sys
from typing import List, Dict, Any

# Add parent directories to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.llm.kimi import get_kimi_client

CLASSIFIER_PROMPT = """
You are an expert NLP classifier. You classify sentences from raw company logs into specific speech-act types.

Here are the 5 speech-act types:
1. CONDITION: Sets the context, timing, or rules under which something applies. Look for keywords like "if", "when", "for customers who", "in the event of".
2. PRESCRIPTION: States a mandatory action, policy rule, requirement, or recommendation of what should happen. (e.g. "Refunds must be requested within 30 days", "gunicorn should be run with gevent").
3. PROCEDURE: Describes step-by-step instructions or operational actions (e.g. "step 1", "first click X", "then run git commit").
4. EXCEPTION: An override to a general rule or an exception condition (e.g. "except for VIPs", "unless the item is damaged").
5. OUTCOME: The result or consequence of an action or rule (e.g. "which returns a 500 error", "so that managers can see their data").

Input format: A JSON list of objects, each containing "id" (integer) and "text" (string).
Output format: You MUST return a JSON list of objects, each containing exactly "id" (integer) and "type" (one of the 5 uppercase strings: CONDITION, PRESCRIPTION, PROCEDURE, EXCEPTION, OUTCOME). Return ONLY valid JSON. No conversational text.

Example Input:
[
  {"id": 0, "text": "If a customer requests a refund after 60 days"},
  {"id": 1, "text": "we must reject the request"}
]

Example Output:
[
  {"id": 0, "type": "CONDITION"},
  {"id": 1, "type": "PRESCRIPTION"}
]
"""

def classify_sentences(sentences: List[str]) -> List[str]:
    """
    Classifies a list of sentences into speech-act types.
    Returns a list of uppercase strings representing the type of each sentence in order.
    """
    if not sentences:
        return []
        
    client = get_kimi_client()
    
    # Format input payload
    input_data = [{"id": i, "text": text} for i, text in enumerate(sentences)]
    
    messages = [
        {"role": "system", "content": CLASSIFIER_PROMPT},
        {"role": "user", "content": json.dumps(input_data)}
    ]
    
    try:
        # Call Kimi client
        raw_response = client.chat_completion(messages, temperature=0.1)
        # Parse JSON
        clean_text = raw_response.strip()
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0].strip()
            
        data = json.loads(clean_text)
        
        # Build lookup dict
        type_map = {item["id"]: item["type"] for item in data if "id" in item and "type" in item}
        
        # Build result list in original order, with default fallback to 'OUTCOME' if missing
        results = []
        for i in range(len(sentences)):
            t = type_map.get(i, "OUTCOME")
            if t not in ["CONDITION", "PRESCRIPTION", "PROCEDURE", "EXCEPTION", "OUTCOME"]:
                t = "OUTCOME"
            results.append(t)
        return results
        
    except Exception as e:
        print(f"Classifier error: {e}. Falling back to default 'PRESCRIPTION' classification.")
        # Fallback in case of API failure or JSON parse issues
        return ["PRESCRIPTION" for _ in sentences]

if __name__ == '__main__':
    # Test stub run
    os.environ["AZURE_ENDPOINT"] = "mock_endpoint"
    os.environ["AZURE_API_KEY"] = "mock_key"
    test_sentences = [
        "If the query latency exceeds 200ms",
        "you should investigate the HNSW index settings",
        "First compile the binary, then copy it to the bin directory"
    ]
    try:
        res = classify_sentences(test_sentences)
        print("Test Classification results:", res)
    except Exception as e:
        print("Expected mock failure:", e)
