import os
import sys
import json
import time
import requests

def score_answer(question, gold_answer, candidate_answer):
    url = "http://127.0.0.1:11434/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    
    prompt = f"""
You are an expert evaluator. Your task is to evaluate the accuracy of a candidate answer against a reference gold answer for a given question.

Question: {question}
Gold Reference Answer: {gold_answer}
Candidate Answer: {candidate_answer}

Grade the candidate answer on a scale of 1 to 5 for factual accuracy relative to the gold answer:
- 5: Fully correct. Matches all facts in the gold answer.
- 4: Mostly correct. Matches core facts, minor details might be missing or slightly off, but no contradiction.
- 3: Partially correct. Captures some facts, but misses significant core facts or has slight contradictions.
- 2: Mostly incorrect. Fails to capture core facts, or contains significant contradictions, but has some relevance.
- 1: Completely incorrect/irrelevant/hallucinated.

Respond ONLY with a valid JSON object containing:
- "score": (integer 1 to 5)
- "reason": (string explaining the score)

No conversational text.
"""
    payload = {
        "model": "qwen2.5:1.5b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 512,
        "response_format": {"type": "json_object"}
    }
    
    for attempt in range(3):
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=30)
            res.raise_for_status()
            data = res.json()
            content = data['choices'][0]['message']['content'].strip()
            score_data = json.loads(content)
            return int(score_data["score"]), score_data["reason"]
        except Exception as e:
            time.sleep(1)
            
    # Default fallback
    return 1, "Failed to evaluate due to API error"

def main():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    cortex_path = os.path.join(base_dir, 'eval', 'cortex_v1.json')
    rag_path = os.path.join(base_dir, 'eval', 'rag_baseline.json')
    output_report_path = os.path.join(base_dir, 'eval', 'benchmark_report.json')
    
    if not os.path.exists(cortex_path):
        print(f"Error: {cortex_path} not found.")
        sys.exit(1)
    if not os.path.exists(rag_path):
        print(f"Error: {rag_path} not found.")
        sys.exit(1)
        
    with open(cortex_path, 'r', encoding='utf-8') as f:
        cortex_results = json.load(f)
    with open(rag_path, 'r', encoding='utf-8') as f:
        rag_results = json.load(f)
        
    # Create lookup map for RAG results by question
    rag_map = {item['question']: item['rag_answer'] for item in rag_results}
    
    scored_results = []
    
    total = len(cortex_results)
    print(f"Starting auto-evaluation of {total} answers...")
    
    cortex_total_score = 0
    rag_total_score = 0
    cortex_wins = 0
    rag_wins = 0
    ties = 0
    
    for idx, item in enumerate(cortex_results):
        question = item['question']
        gold = item['gold_answer']
        cortex_ans = item['cortex_answer']
        rag_ans = rag_map.get(question, "N/A")
        
        print(f"\n[{idx+1}/{total}] Question: {question}")
        
        cortex_score, cortex_reason = score_answer(question, gold, cortex_ans)
        rag_score, rag_reason = score_answer(question, gold, rag_ans)
        
        print(f"  Cortex Score: {cortex_score}/5 ({cortex_reason[:60]}...)")
        print(f"  RAG Score: {rag_score}/5 ({rag_reason[:60]}...)")
        
        cortex_total_score += cortex_score
        rag_total_score += rag_score
        
        if cortex_score > rag_score:
            cortex_wins += 1
            comparison = "CORTEX_WIN"
        elif rag_score > cortex_score:
            rag_wins += 1
            comparison = "RAG_WIN"
        else:
            ties += 1
            comparison = "TIE"
            
        scored_results.append({
            "question": question,
            "gold_answer": gold,
            "cortex_answer": cortex_ans,
            "cortex_score": cortex_score,
            "cortex_reason": cortex_reason,
            "rag_answer": rag_ans,
            "rag_score": rag_score,
            "rag_reason": rag_reason,
            "comparison": comparison
        })
        
    cortex_avg = cortex_total_score / total
    rag_avg = rag_total_score / total
    
    report = {
        "summary": {
            "total_questions": total,
            "cortex_average_score": round(cortex_avg, 2),
            "rag_average_score": round(rag_avg, 2),
            "cortex_win_rate": round(cortex_wins / total * 100, 1),
            "rag_win_rate": round(rag_wins / total * 100, 1),
            "tie_rate": round(ties / total * 100, 1),
            "cortex_wins": cortex_wins,
            "rag_wins": rag_wins,
            "ties": ties
        },
        "details": scored_results
    }
    
    with open(output_report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
        
    print("\n==================================================")
    print("EVALUATION COMPLETED AND SAVED!")
    print(f"Cortex Average Score: {report['summary']['cortex_average_score']}/5")
    print(f"RAG Average Score:    {report['summary']['rag_average_score']}/5")
    print(f"Cortex Wins: {cortex_wins} | RAG Wins: {rag_wins} | Ties: {ties}")
    print("==================================================")

if __name__ == '__main__':
    main()
