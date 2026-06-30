from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


def content_hash(value: Any) -> str:
    if isinstance(value, str):
        data = value
    else:
        data = json.dumps(value, sort_keys=True, default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


class NormalizedSourceObject(BaseModel):
    tenant_id: str
    connector_type: str
    external_id: str
    object_type: str
    title: str
    url: Optional[str] = None
    author: Optional[str] = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    raw_json: Dict[str, Any] = Field(default_factory=dict)
    content_hash: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def fill_hash(self) -> "NormalizedSourceObject":
        if not self.content_hash:
            self.content_hash = content_hash(
                {
                    "external_id": self.external_id,
                    "title": self.title,
                    "raw_json": self.raw_json,
                    "metadata": self.metadata,
                }
            )
        return self


class NormalizedSourceDocument(BaseModel):
    source_object_external_id: str
    title: str
    body_text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    content_hash: str = ""

    @model_validator(mode="after")
    def validate_document(self) -> "NormalizedSourceDocument":
        if not self.body_text.strip():
            raise ValueError("source document requires body_text")
        if not self.content_hash:
            self.content_hash = content_hash(self.body_text)
        return self


class NormalizedSourceSegment(BaseModel):
    document_ref: str
    segment_type: str = "paragraph"
    heading_path: List[str] = Field(default_factory=list)
    position: int
    text: str
    author: Optional[str] = None
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    content_hash: str = ""

    @model_validator(mode="after")
    def validate_segment(self) -> "NormalizedSourceSegment":
        if self.position < 0:
            raise ValueError("source segment position must be >= 0")
        if not self.text.strip():
            raise ValueError("source segment requires text")
        if not self.content_hash:
            self.content_hash = content_hash(
                {
                    "document_ref": self.document_ref,
                    "position": self.position,
                    "text": self.text,
                }
            )
        return self


class NormalizedSourceRelationship(BaseModel):
    from_external_id: str
    to_external_id: str
    relationship_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NormalizedSourceBundle(BaseModel):
    tenant_id: str
    connector_type: str
    objects: List[NormalizedSourceObject] = Field(default_factory=list)
    documents: List[NormalizedSourceDocument] = Field(default_factory=list)
    segments: List[NormalizedSourceSegment] = Field(default_factory=list)
    relationships: List[NormalizedSourceRelationship] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_bundle(self) -> "NormalizedSourceBundle":
        if not self.documents:
            raise ValueError("normalized source bundle requires at least one document")
        return self


class EngineStageResult(BaseModel):
    stage: str
    ok: bool
    counts: Dict[str, int] = Field(default_factory=dict)
    failures: List[str] = Field(default_factory=list)


class EngineIngestResult(BaseModel):
    tenant_id: str
    ok: bool
    stage_results: List[EngineStageResult] = Field(default_factory=list)
    failures: List[str] = Field(default_factory=list)
    counts: Dict[str, int] = Field(default_factory=dict)


class DraftCompileResult(BaseModel):
    ok: bool
    draft_ids: List[str] = Field(default_factory=list)
    failures: List[str] = Field(default_factory=list)


class ApprovalResult(BaseModel):
    ok: bool
    draft_id: str
    page_id: Optional[str] = None
    commit_sha: Optional[str] = None
    failures: List[str] = Field(default_factory=list)
