# Data Model: Notion Ingestion & Page Validation Fixes

## 1. Database Schema Additions

### Table: `notion_objects`
This table tracks all Notion pages and databases discovered during the Notion search/crawling phase. It ensures we have a registry of what is accessible, what has been skipped, and what has been successfully ingested.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `notion_id` | TEXT | PRIMARY KEY | The UUID of the page or database in Notion |
| `tenant_id` | TEXT | FOREIGN KEY | References `tenants(id)` |
| `title` | TEXT | NOT NULL | Title of the page or database |
| `url` | TEXT | NOT NULL | Notion URL of the object |
| `parent_id` | TEXT | NULLABLE | ID of parent page/database for hierarchy tracking |
| `last_edited_time` | TEXT | NOT NULL | Notion's last edit timestamp |
| `type` | TEXT | NOT NULL | `'page'` or `'database'` |
| `sync_status` | TEXT | NOT NULL | `'discovered'`, `'synced'`, `'failed'`, `'empty'`, `'inaccessible'` |
| `error_message` | TEXT | NULLABLE | Error details if sync/extraction fails |
| `last_synced_at` | DATETIME | NULLABLE | When it was last compiled into a SourceDocument |

### Table Updates: `ingestion_jobs`
We will ensure `ingestion_jobs` contains clear fields for tracking validator results:

| Column | Type | Description |
|--------|------|-------------|
| `failure_reason` | TEXT | Store validation errors (e.g. "Missing YAML header", "Contains LLM leakage </output_format>") or fetch errors |

---

## 2. Ingestion Source Data Model

### SourceDocument Entity
When Notion (or any connector) crawler extracts raw text, it will package the data in a `SourceDocument` Pydantic model:

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class SourceBlock(BaseModel):
    block_id: str
    type: str  # e.g., heading_1, paragraph, code
    content: str
    parent_id: Optional[str] = None

class SourceDocument(BaseModel):
    id: str  # e.g., notion://page/{uuid}
    tenant_id: str
    title: str
    url: str
    raw_markdown: str
    blocks: List[SourceBlock] = Field(default_factory=list)
```

### IngestedPage YAML Frontmatter Schema
Synthesized files must adhere strictly to this YAML schema before being committed:

```yaml
---
id: "page_007"
title: "Flowgent Integration Guidelines"
sources:
  - "notion://page/user_3FFu8d2bNoY8nkiJe2kdIQc6pFZ#block-98124b"
propositions:
  - "Cortex routes propositions through a validation check prior to Git storage."
synthesis_validation:
  completeness_score: 8
  proposition_coverage: 92
  hallucination_rate: 0
---
```
