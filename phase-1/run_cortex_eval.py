"""
run_cortex_eval.py — Evaluate Cortex on 50 ground-truth questions.

Usage:
    python phase-1/run_cortex_eval.py [--tenant-dir PATH]

Outputs:
    phase-1/eval/cortex_v1.json  — answers, latencies, and pages_read per question
"""

import os
import sys
import json
import time
import argparse

# Resolve phase-1 root so app.* imports work
PHASE1_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, PHASE1_DIR)

from app.query_engine import CortexQueryEngine

DEFAULT_TENANT_DIR  = os.path.join(PHASE1_DIR, "data", "tenants", "default")
GROUND_TRUTH_PATH   = os.path.join(PHASE1_DIR, "eval", "ground_truth.json")
OUTPUT_PATH         = os.path.join(PHASE1_DIR, "eval", "cortex_v1.json")


def run_eval(tenant_dir: str):
    print(f"\n=== Cortex Phase-1 Evaluation ===")
    print(f"  Tenant dir   : {tenant_dir}")
    print(f"  Ground truth : {GROUND_TRUTH_PATH}")
    print(f"  Output       : {OUTPUT_PATH}\n")

    # Load engine once
    engine = CortexQueryEngine(tenant_dir=tenant_dir, top_k=3)

    # Load ground truth
    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
        qa_pairs = json.load(f)

    results = []
    total_questions = len(qa_pairs)

    for idx, pair in enumerate(qa_pairs):
        question    = pair["question"]
        gold_answer = pair.get("answer", "")

        print(f"[{idx+1:2d}/{total_questions}] {question[:90]}...")
        try:
            result = engine.query(question)
            results.append({
                "question":       question,
                "gold_answer":    gold_answer,
                "cortex_answer":  result["answer"],
                "pages_read":     result["pages_read"],
                "pages_read_count": result["pages_read_count"],
                "total_latency_ms": result["total_latency_ms"],
                "traversal_path": result["traversal_path"],
                "knowledge_gaps": result["knowledge_gaps"],
            })
            print(f"         Answer preview: {result['answer'][:120]}...")
        except Exception as e:
            print(f"         ERROR: {e}")
            results.append({
                "question":       question,
                "gold_answer":    gold_answer,
                "cortex_answer":  f"ERROR: {e}",
                "pages_read":     [],
                "pages_read_count": 0,
                "total_latency_ms": 0,
                "traversal_path": [],
                "knowledge_gaps": [],
            })

    # Save results
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Print summary stats
    answered   = sum(1 for r in results if not r["cortex_answer"].startswith("ERROR"))
    avg_lat    = sum(r["total_latency_ms"] for r in results if r["total_latency_ms"]) / max(answered, 1)
    avg_pages  = sum(r["pages_read_count"] for r in results) / max(len(results), 1)

    print(f"\n=== Evaluation Summary ===")
    print(f"  Total questions  : {total_questions}")
    print(f"  Successfully answered : {answered}")
    print(f"  Avg latency       : {avg_lat:.0f} ms")
    print(f"  Avg pages read    : {avg_pages:.1f}")
    print(f"  Results saved to  : {OUTPUT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cortex Phase-1 Evaluation Runner")
    parser.add_argument("--tenant-dir", default=DEFAULT_TENANT_DIR)
    args = parser.parse_args()

    # Default to Groq if not configured
    if not os.environ.get("LLM_PROVIDER"):
        os.environ["LLM_PROVIDER"]     = "web_api"
    if not os.environ.get("AZURE_ENDPOINT") and not os.environ.get("WEB_API_ENDPOINT"):
        os.environ["AZURE_ENDPOINT"]   = "https://api.groq.com/openai/v1"
    if not os.environ.get("AZURE_API_KEY") and not os.environ.get("WEB_API_KEY"):
        os.environ["AZURE_API_KEY"]    = ""
    if not os.environ.get("AZURE_MODEL_NAME") and not os.environ.get("WEB_API_MODEL"):
        os.environ["AZURE_MODEL_NAME"] = "llama-3.1-8b-instant"

    run_eval(args.tenant_dir)
