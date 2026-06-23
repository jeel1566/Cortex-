import os
import requests
from typing import List, Dict, Any

class NotionClient:
    """
    Client wrapper for the Notion API.
    Fetches updated pages from a workspace database using poll-based retrieval,
    and extracts full text block contents.
    """
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("NOTION_API_KEY", "mock_notion_key")
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

    def fetch_page_content(self, page_id: str) -> str:
        """
        Recursively fetches the block children of a page and converts them into markdown-like text.
        """
        if self.api_key == "mock_notion_key":
            return (
                "## Setup Guide\n"
                "To deploy the application securely, you should run Gunicorn as the WSGI server "
                "with gevent workers behind an Nginx reverse proxy. Ensure you set the worker timeout "
                "to at least 60 seconds to accommodate slow LLM retrieval steps."
            )

        url = f"{self.base_url}/blocks/{page_id}/children"
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            blocks = []
            for block in data.get("results", []):
                block_type = block.get("type")
                if not block_type:
                    continue
                
                content = block.get(block_type, {})
                rich_text = content.get("rich_text", [])
                
                text_val = ""
                if rich_text:
                    text_val = "".join([t.get("text", {}).get("content", "") for t in rich_text])
                
                if block_type.startswith("heading_"):
                    level = block_type.split("_")[1]
                    blocks.append(f"{'#' * int(level)} {text_val}")
                elif block_type == "paragraph":
                    blocks.append(text_val)
                elif block_type == "bulleted_list_item":
                    blocks.append(f"- {text_val}")
                elif block_type == "numbered_list_item":
                    blocks.append(f"1. {text_val}")
                elif block_type == "code":
                    code_text = "".join([t.get("text", {}).get("content", "") for t in content.get("rich_text", [])])
                    blocks.append(f"```\n{code_text}\n```")
                elif block_type == "quote":
                    blocks.append(f"> {text_val}")
                
            return "\n\n".join(blocks)
        except Exception as e:
            print(f"Error querying Notion page blocks: {e}")
            return ""

    def fetch_database_updates(self, database_id: str, last_edited_since_iso: str) -> List[Dict[str, Any]]:
        """
        Queries a Notion database for pages edited since a specific ISO timestamp.
        Returns a list of simplified message structures with full page text contents.
        """
        # Under offline or mock environment, return simulated updates
        if self.api_key == "mock_notion_key":
            mock_text = self.fetch_page_content("mock_page_1")
            return [
                {
                    "text": f"Document Title: The WSGI server for Superset.\n\n{mock_text}",
                    "user": "notion_sync_bot",
                    "channel": "notion_kb",
                    "timestamp": last_edited_since_iso,
                    "source_id": f"notion://page/mock_page_1"
                }
            ]

        url = f"{self.base_url}/databases/{database_id}/query"
        payload = {
            "filter": {
                "property": "Last Edited Time",
                "date": {
                    "after": last_edited_since_iso
                }
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for page in data.get("results", []):
                page_id = page.get("id")
                # Parse simplified text properties
                title = "Untitled Page"
                properties = page.get("properties", {})
                for prop_name, prop_val in properties.items():
                    if prop_val.get("type") == "title":
                        title_list = prop_val.get("title", [])
                        if title_list:
                            title = title_list[0].get("text", {}).get("content", "Untitled Page")
                            break
                            
                # Retrieve actual page body text from block children
                page_body = self.fetch_page_content(page_id)
                full_text = f"Document Title: {title}\n\n{page_body}" if page_body else f"Document Title: {title}"
                
                results.append({
                    "text": full_text,
                    "user": "notion_sync_bot",
                    "channel": "notion_kb",
                    "timestamp": page.get("last_edited_time", ""),
                    "source_id": f"notion://page/{page_id}"
                })
            return results
        except Exception as e:
            print(f"Error querying Notion API: {e}")
            return []
