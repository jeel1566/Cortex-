# RAG Baseline Evaluation Report

This report evaluates the local RAG baseline run (`phase-1/eval/rag_baseline.json`) against the human-verified ground truth dataset (`phase-1/eval/ground_truth.json`).

---

## 📊 Performance Benchmark Summary

| Metric | Value | Percentage | Description |
| :--- | :---: | :---: | :--- |
| **Total Questions** | 50 | 100% | Full ground truth Q&A set |
| **Fully Correct** | 29 | 58% | Factual, complete, and cited correctly |
| **Partially Correct** | 5 | 10% | Correct details but missing specific points or slightly mismatched |
| **Incorrect / Failed** | 16 | 32% | Returned incorrect info, missing info, or failed due to redaction |
| **Average Score** | **3.4 / 5.0** | - | Based on accuracy, completeness, and attribution |

---

## 🔍 Failure Analysis & Key Insights

Analyzing the 16 failed or incorrect answers revealed two **major system bugs** in the baseline pipeline:

### 1. 🚨 PII Over-Redaction Bug (Critical)
* **The Issue**: The PII redaction regex in `local_rag.py` is too greedy:
  ```python
  text = re.sub(r'\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}', '[PHONE]', text)
  ```
  It accidentally matches dates (like `2020-08-04`) and GitHub Pull Request numbers (like `#10345`), redacting them into `[PHONE]`.
* **Impact**:
  * **Q15**: Failed to retrieve PR number for fixing Slack integration because the PR was redacted.
  * **Q18**: Redacted the date in the BigQuery blog post link (`preset.io/blog/[PHONE]-google-bigquery/`).
  * **Q42**: Failed to resolve the pull request number for fixing Slack integration.

### 2. 👤 User ID Anonymization Bug (Critical)
* **The Issue**: Mentions of original Slack User IDs (e.g. `<@U017193F7JQ>`, `UH0UPCJVD`) are replaced with mapped names (e.g. `Ryan`, `Ariana Atnip`) and the original IDs are discarded.
* **Impact**:
  * When a question asks about a specific User ID (e.g., "What did user U016M4223HA ask help for?"), the retriever and LLM fail because the literal text `U016M4223HA` has been scrubbed from the ingested messages.
  * **Q22, Q27, Q31, Q33, Q48, Q49** all failed because the query specified a Slack User ID that was not indexed.

### 3. 📂 Retrieval Gaps (Scope Limitations)
* **The Issue**: Naive retrieval over Slack threads is insufficient for files outside of Slack conversations.
* **Impact**:
  * **Q23** (merging migrations in `Contributing.md`) and **Q37** (WSGI server in Superset docs) failed because the documentation files were either not indexed or not retrieved within the top-k Slack context.

---

## 📋 Direct Comparisons of Key Questions

| Question | Gold Answer | RAG Answer | Status | Notes |
| :--- | :--- | :--- | :---: | :--- |
| **Q1: Who started Superset and when?** | Max in 2015 at Airbnb | Majorie Montano in 2015 at Airbnb | ❌ **Incorrect** | Retrieved wrong user from the thread |
| **Q15: PR for fixing Slack integration?** | Pull request #10345 | Not provided / redacted to `[PHONE]` | ❌ **Failed** | PII redaction bug |
| **Q27: ECharts chart recommended?** | ECharts 3D surface chart | Surface chart recommended by Ariana Atnip | ⚠️ **Partial** | Mapped user ID UH0UPCJVD to name |
| **Q32: statsd-host in gunicorn?** | `localhost:8125` | `localhost:8125` |  **Correct** | Accurate extraction |

---

## 🚀 What to Do Next (Based on Cortex Roadmap)

Per the **Cortex implementation plan** (`06-cortex-implementation.md`), we are currently at **Day 1 (Prove it works)**. To proceed:

1. **Fix the Ingestion Redaction & Mapping Bugs (Immediate Action)**:
   * Refine the PII regex in `app/llm/kimi.py` to prevent redacting dates or PR numbers.
   * Maintain a dual-index mapping or keep the original user IDs in brackets (e.g., `Real Name [U12345]`) so queries referencing Slack IDs can still resolve.

2. **Transition to Day 2 (Local Embeddings & Indexing)**:
   * Create `app/llm/embedding.py` using `fastembed` with the `BAAI/bge-small-en-v1.5` model.
   * Integrate the embedding module with the `hnswlib` vector index.
   * Validate the `POST /v1/query` endpoint for local page retrieval in <200ms.

3. **Transition to Day 3 & 4 (Ingestion & Validation)**:
   * Replace classifier and clusterer stubs with real LLM calls.
   * Implement synthesis validation (proposition coverage, hallucination check, completeness scores).
