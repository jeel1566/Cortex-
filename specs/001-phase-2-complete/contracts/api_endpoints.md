# API Interface Contracts: Phase 2 — Make it Complete

All HTTP requests and responses use JSON and require an Authorization Header: `Authorization: Bearer <clerk_jwt_token>`.

---

## 1. POST /v1/query
Submit a natural language question and obtain the matching pages and traversal path.

### Request Body
```json
{
  "question": "What is the standard refund policy for late shipments?",
  "time_budget_ms": 150
}
```

### Response (200 OK)
```json
{
  "query_id": "q_abc123",
  "pages": [
    {
      "id": "page_013",
      "title": "Standard Refund Policy",
      "version": 3,
      "content": "Refunds are processed within 5 days...",
      "last_updated": "2026-01-15T09:00:00Z",
      "owner": "finance_team",
      "access_level": "team",
      "synthesis_validation": {
        "proposition_coverage": 0.94,
        "hallucination_rate": 0.00,
        "completeness_score": 8.5
      }
    }
  ],
  "traversal_path": [
    {
      "from": "vector_safety_net",
      "to": "page_013",
      "link_type": "vector_fallback",
      "condition_matched": "similarity_0.82"
    }
  ],
  "knowledge_gaps": [],
  "overall_confidence": 0.92,
  "total_latency_ms": 78,
  "pages_read": 1
}
```

---

## 2. GET /v1/page/:id
Retrieve the complete details of a specific knowledge page.

### Response (200 OK)
```json
{
  "id": "page_013",
  "title": "Standard Refund Policy",
  "version": 3,
  "last_updated": "2026-01-15T09:00:00Z",
  "owner": "finance_team",
  "access_level": "team",
  "primary_links": ["page_042"],
  "secondary_links": [
    {
      "condition": "damaged OR defect OR broken",
      "page": "page_055"
    }
  ],
  "synthesis_validation": {
    "proposition_coverage": 0.94,
    "hallucination_rate": 0.00,
    "completeness_score": 8.5
  },
  "sources": [
    "slack://C123ABC/1705312800"
  ]
}
```

---

## 3. POST /v1/ingest
Initiate a new ingestion job for logs or files.

### Request Body
```json
{
  "source_type": "slack",
  "content": "raw log or file contents",
  "metadata": {
    "author": "john.doe",
    "timestamp": "2026-06-17T10:00:00Z",
    "urgency": "standard"
  }
}
```

### Response (202 Accepted)
```json
{
  "job_id": "job_xyz789",
  "status": "queued",
  "estimated_completion_ms": 3000,
  "poll_url": "/v1/ingest/job_xyz789"
}
```

---

## 4. GET /v1/ingest/:job_id
Check the progress and results of an ingestion job.

### Response (200 OK)
```json
{
  "job_id": "job_xyz789",
  "status": "complete",
  "pages_created": 2,
  "pages_updated": 0,
  "conflicts_found": 0,
  "completed_at": "2026-06-17T10:00:05Z"
}
```

---

## 5. POST /v1/feedback
Submit feedback when a page or response is incorrect or out of date.

### Request Body
```json
{
  "query_id": "q_abc123",
  "feedback_type": "wrong_answer",
  "affected_pages": ["page_013"],
  "correct_answer": "Refund window is now 60 days instead of 30."
}
```

### Response (200 OK)
```json
{
  "feedback_id": "fb_111222",
  "status": "received",
  "pages_flagged": ["page_013"],
  "resynthesis_queued": true
}
```
