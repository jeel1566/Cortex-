from typing import List, Dict, Any, Optional
from app.ingestion.connectors.base import ConnectorAdapter
from app.ingestion.engine_models import (
    NormalizedSourceBundle,
    NormalizedSourceObject,
    NormalizedSourceDocument,
    NormalizedSourceSegment,
    NormalizedSourceRelationship,
)

class GoogleDocsAdapter(ConnectorAdapter):
    def __init__(self, tenant_id: str, doc_id: str, credentials_token: str):
        self.tenant_id = tenant_id
        self.doc_id = doc_id
        self.credentials_token = credentials_token
        if self.credentials_token == "mock_gdocs_token":
            import os
            allow_mock = os.environ.get("ALLOW_MOCK_CONNECTORS", "").lower() in {"1", "true", "yes"}
            if not allow_mock:
                raise ValueError("GOOGLE_DOCS_TOKEN is not configured. Set it or enable ALLOW_MOCK_CONNECTORS=1 for demo syncs.")

    def fetch_document_content(self) -> Dict[str, Any]:
        if self.credentials_token == "mock_gdocs_token":
            return {
                "title": "Project Proposal",
                "documentId": self.doc_id,
                "body": {
                    "content": [
                        {
                            "paragraph": {
                                "elements": [{"textRun": {"content": "Project Proposal\n"}}],
                                "paragraphStyle": {"namedStyleType": "TITLE"}
                            }
                        },
                        {
                            "paragraph": {
                                "elements": [{"textRun": {"content": "Introduction\n"}}],
                                "paragraphStyle": {"namedStyleType": "HEADING_1"}
                            }
                        },
                        {
                            "paragraph": {
                                "elements": [{"textRun": {"content": "This is a new project for team space.\n"}}],
                                "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"}
                            }
                        },
                        {
                            "table": {
                                "tableRows": [
                                    {
                                        "tableCells": [
                                            {
                                                "content": [
                                                    {
                                                        "paragraph": {
                                                            "elements": [{"textRun": {"content": "Metric Name\n"}}]
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                "content": [
                                                    {
                                                        "paragraph": {
                                                            "elements": [{"textRun": {"content": "Value\n"}}]
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "tableCells": [
                                            {
                                                "content": [
                                                    {
                                                        "paragraph": {
                                                            "elements": [{"textRun": {"content": "Target NPS\n"}}]
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                "content": [
                                                    {
                                                        "paragraph": {
                                                            "elements": [{"textRun": {"content": "75\n"}}]
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        }
                    ]
                }
            }

        import requests
        url = f"https://docs.googleapis.com/v1/documents/{self.doc_id}"
        headers = {"Authorization": f"Bearer {self.credentials_token}"}
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error fetching Google Doc content: {e}")
            return {}

    def extract_text_from_elements(self, elements: List[Dict[str, Any]]) -> str:
        text = ""
        for el in elements:
            if "textRun" in el:
                text += el["textRun"].get("content", "")
        return text.strip()

    def normalize(self) -> NormalizedSourceBundle:
        doc_data = self.fetch_document_content()
        if not doc_data:
            raise ValueError(f"No content fetched for Google Doc {self.doc_id}")

        title = doc_data.get("title", "Untitled Google Doc")
        external_id = f"google_docs://doc/{self.doc_id}"

        src_obj = NormalizedSourceObject(
            tenant_id=self.tenant_id,
            connector_type="google_docs",
            external_id=external_id,
            object_type="document",
            title=title,
            url=f"https://docs.google.com/document/d/{self.doc_id}/edit",
            metadata={"doc_id": self.doc_id},
        )

        segments = []
        body_parts = []
        position = 0
        current_heading_path = []

        content_list = doc_data.get("body", {}).get("content", [])
        for item in content_list:
            if "paragraph" in item:
                para = item["paragraph"]
                text = self.extract_text_from_elements(para.get("elements", []))
                if not text:
                    continue
                
                style = para.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
                
                if style.startswith("HEADING_") or style == "TITLE":
                    try:
                        level = int(style.split("_")[1]) if style.startswith("HEADING_") else 1
                    except ValueError:
                        level = 1
                    
                    if len(current_heading_path) >= level:
                        current_heading_path = current_heading_path[:level - 1]
                    while len(current_heading_path) < level - 1:
                        current_heading_path.append("")
                    current_heading_path.append(text)
                    
                    segments.append(NormalizedSourceSegment(
                        document_ref=external_id,
                        segment_type="heading",
                        heading_path=list(current_heading_path),
                        position=position,
                        text=text,
                        metadata={"heading_level": level, "paragraph_style": style}
                    ))
                    position += 1
                else:
                    segments.append(NormalizedSourceSegment(
                        document_ref=external_id,
                        segment_type="paragraph",
                        heading_path=list(current_heading_path),
                        position=position,
                        text=text,
                        metadata={"paragraph_style": style}
                    ))
                    position += 1
                body_parts.append(text)

            elif "table" in item:
                table = item["table"]
                for row_idx, row in enumerate(table.get("tableRows", [])):
                    row_texts = []
                    for cell in row.get("tableCells", []):
                        cell_text = ""
                        for cell_item in cell.get("content", []):
                            if "paragraph" in cell_item:
                                cell_text += self.extract_text_from_elements(cell_item["paragraph"].get("elements", []))
                        row_texts.append(cell_text.strip())
                    
                    if any(row_texts):
                        text = " | ".join(row_texts)
                        segments.append(NormalizedSourceSegment(
                            document_ref=external_id,
                            segment_type="table_row",
                            heading_path=list(current_heading_path),
                            position=position,
                            text=text,
                            metadata={"table_info": {"row_index": row_idx}}
                        ))
                        position += 1
                        body_parts.append(text)

        body_text = "\n\n".join(body_parts)
        if not body_text.strip():
            raise ValueError("Zero documents discovered from Google Docs. Google Docs empty sync must fail loudly.")
            
        doc = NormalizedSourceDocument(
            source_object_external_id=external_id,
            title=title,
            body_text=body_text,
            metadata={"doc_id": self.doc_id},
        )

        return NormalizedSourceBundle(
            tenant_id=self.tenant_id,
            connector_type="google_docs",
            objects=[src_obj],
            documents=[doc],
            segments=segments,
            relationships=[]
        )
