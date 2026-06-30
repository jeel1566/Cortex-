from typing import List, Dict, Any, Optional
from app.ingestion.connectors.base import ConnectorAdapter
from app.ingestion.notion import NotionClient
from app.ingestion.engine_models import (
    NormalizedSourceBundle,
    NormalizedSourceObject,
    NormalizedSourceDocument,
    NormalizedSourceSegment,
    NormalizedSourceRelationship,
)

class NotionAdapter(ConnectorAdapter):
    def __init__(self, tenant_id: str, api_key: str, database_id: Optional[str] = None):
        self.tenant_id = tenant_id
        self.api_key = api_key
        self.database_id = database_id or ""
        self.client = NotionClient(api_key=api_key)

    def discover(self) -> List[Dict[str, Any]]:
        discovered = self.client.discover_objects()
        if self.database_id:
            discovered = [
                obj for obj in discovered 
                if obj["id"] == self.database_id or obj.get("parent_id") == self.database_id
            ]
        return discovered

    def normalize(self) -> NormalizedSourceBundle:
        discovered = self.discover()
        pages = [obj for obj in discovered if obj["type"] == "page"]
        
        if not pages:
            raise ValueError("Zero pages discovered from Notion. Notion empty sync must fail loudly.")
            
        objects = []
        documents = []
        segments = []
        relationships = []
        skipped_empty = 0
        
        for page in pages:
            external_id = f"notion://page/{page['id']}"
            
            page_body = self.client.fetch_page_content(page["id"])
            if not page_body.strip():
                import logging
                logging.getLogger("notion").warning(f"Skipping empty Notion page {page['title']} ({page['id']})")
                skipped_empty += 1
                continue
                
            src_obj = NormalizedSourceObject(
                tenant_id=self.tenant_id,
                connector_type="notion",
                external_id=external_id,
                object_type="page",
                title=page["title"],
                url=page["url"],
                metadata={"last_edited_time": page.get("last_edited_time", "")},
            )
            objects.append(src_obj)
            
            doc = NormalizedSourceDocument(
                source_object_external_id=external_id,
                title=page["title"],
                body_text=page_body,
                metadata={"last_edited_time": page.get("last_edited_time", "")},
            )
            documents.append(doc)
            
            # Use Markdown parsing logic to split page body into segments
            from app.ingestion.connectors.local_upload import LocalUploadAdapter
            dummy_adapter = LocalUploadAdapter(self.tenant_id, "dummy.md")
            raw_segments = dummy_adapter._parse_markdown(page_body)
            
            position = 0
            for s in raw_segments:
                if s["segment_type"] == "heading":
                    segments.append(NormalizedSourceSegment(
                        document_ref=external_id,
                        segment_type="heading",
                        heading_path=s["heading_path"],
                        position=position,
                        text=s["text"],
                    ))
                    position += 1
                elif "|" in s["text"]:
                    lines = [line.strip() for line in s["text"].splitlines() if line.strip()]
                    for line in lines:
                        segments.append(NormalizedSourceSegment(
                            document_ref=external_id,
                            segment_type="table_row",
                            heading_path=s["heading_path"],
                            position=position,
                            text=line,
                        ))
                        position += 1
                else:
                    segments.append(NormalizedSourceSegment(
                        document_ref=external_id,
                        segment_type="paragraph",
                        heading_path=s["heading_path"],
                        position=position,
                        text=s["text"],
                    ))
                    position += 1
                
            if page.get("parent_id"):
                relationships.append(NormalizedSourceRelationship(
                    from_external_id=f"notion://page/{page['parent_id']}",
                    to_external_id=external_id,
                    relationship_type="child_of"
                ))
                
        if not documents:
            raise ValueError("Zero pages discovered from Notion. Notion empty sync must fail loudly.")
                
        return NormalizedSourceBundle(
            tenant_id=self.tenant_id,
            connector_type="notion",
            objects=objects,
            documents=documents,
            segments=segments,
            relationships=relationships,
            skipped_empty_count=skipped_empty
        )
