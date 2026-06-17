import os
import requests
from typing import List, Dict, Any

class NotionClient:
    """
    Client wrapper for the Notion API.
    Fetches updated pages from a workspace database using poll-based retrieval.
    """
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("NOTION_API_KEY", "mock_notion_key")
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

    def fetch_database_updates(self, database_id: str, last_edited_since_iso: str) -> List[Dict[str, Any]]:
        """
        Queries a Notion database for pages edited since a specific ISO timestamp.
        Returns a list of simplified message structures for ingestion.
        """
        # Under offline or mock environment, return simulated updates
        if self.api_key == "mock_notion_key":
            return [
                {
                    "text": "The WSGI server for Superset should be Gunicorn running with gevent workers.",
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
                            
                results.append({
                    "text": f"Document Title: {title}. Page ID: {page_id}.",
                    "user": "notion_sync_bot",
                    "channel": "notion_kb",
                    "timestamp": page.get("last_edited_time", ""),
                    "source_id": f"notion://page/{page_id}"
                })
            return results
        except Exception as e:
            print(f"Error querying Notion API: {e}")
            return []
