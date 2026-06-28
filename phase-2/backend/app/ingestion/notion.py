import os
import requests
import datetime
from typing import List, Dict, Any, Optional

class NotionClient:
    """
    Client wrapper for the Notion API.
    Fetches updated pages from a workspace database using poll-based retrieval,
    and extracts full text block contents recursively.
    """
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("NOTION_API_KEY", "mock_notion_key")
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

    def fetch_block_children(self, block_id: str, depth: int = 0) -> List[str]:
        """
        Recursively fetches child blocks of a given block up to depth 5.
        Converts blocks (headings, paragraphs, lists, tables, callouts) to Markdown.
        """
        if depth > 5:
            return []

        url = f"{self.base_url}/blocks/{block_id}/children"
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            blocks = []
            indent = "  " * depth
            for block in data.get("results", []):
                block_id_val = block.get("id")
                block_type = block.get("type")
                if not block_type:
                    continue
                
                content = block.get(block_type, {})
                rich_text = content.get("rich_text", [])
                
                text_val = ""
                if rich_text:
                    text_val = "".join([t.get("text", {}).get("content", "") for t in rich_text])
                
                has_children = block.get("has_children", False)
                child_lines = []
                if has_children:
                    child_lines = self.fetch_block_children(block_id_val, depth + 1)
                
                if block_type.startswith("heading_"):
                    level = block_type.split("_")[1]
                    blocks.append(f"{indent}{'#' * int(level)} {text_val}")
                elif block_type == "paragraph":
                    blocks.append(f"{indent}{text_val}")
                elif block_type == "bulleted_list_item":
                    blocks.append(f"{indent}- {text_val}")
                elif block_type == "numbered_list_item":
                    blocks.append(f"{indent}1. {text_val}")
                elif block_type == "code":
                    code_text = "".join([t.get("text", {}).get("content", "") for t in content.get("rich_text", [])])
                    blocks.append(f"{indent}```\n{code_text}\n```")
                elif block_type == "quote":
                    blocks.append(f"{indent}> {text_val}")
                elif block_type == "callout":
                    blocks.append(f"{indent}> [!NOTE] {text_val}")
                elif block_type == "table":
                    if has_children and child_lines:
                        blocks.extend(child_lines)
                        has_children = False  # already fetched as rows
                elif block_type == "table_row":
                    cells = content.get("cells", [])
                    row_cells = []
                    for cell in cells:
                        cell_text = "".join([t.get("text", {}).get("content", "") for t in cell])
                        row_cells.append(cell_text)
                    blocks.append(f"{indent}| {' | '.join(row_cells)} |")
                
                if has_children and child_lines and block_type != "table":
                    blocks.extend(child_lines)
                    
            return blocks
        except Exception as e:
            print(f"Error querying Notion block children for {block_id}: {e}")
            return []

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

        blocks = self.fetch_block_children(page_id, depth=0)
        return "\n\n".join(blocks)

    def discover_objects(self) -> List[Dict[str, Any]]:
        """
        Discovers all pages and databases accessible by the integration.
        Returns a list of dicts: [
            {"id": str, "title": str, "url": str, "parent_id": str, "last_edited_time": str, "type": "page"|"database"}
        ]
        """
        if self.api_key == "mock_notion_key":
            return [
                {
                    "id": "mock_page_1",
                    "title": "The WSGI server for Superset",
                    "url": "https://notion.so/mock_page_1",
                    "parent_id": None,
                    "last_edited_time": "2026-06-17T00:00:00.000Z",
                    "type": "page"
                },
                {
                    "id": "mock_db_1",
                    "title": "Engineering Wiki Database",
                    "url": "https://notion.so/mock_db_1",
                    "parent_id": None,
                    "last_edited_time": "2026-06-17T00:00:00.000Z",
                    "type": "database"
                }
            ]

        url = f"{self.base_url}/search"
        results = []
        has_more = True
        next_cursor = None

        try:
            while has_more:
                payload = {}
                if next_cursor:
                    payload["start_cursor"] = next_cursor

                response = requests.post(url, json=payload, headers=self.headers, timeout=15)
                response.raise_for_status()
                data = response.json()

                for obj in data.get("results", []):
                    obj_id = obj.get("id")
                    obj_type = obj.get("object")  # 'page' or 'database'
                    if obj_type not in ("page", "database"):
                        continue

                    # Extract title
                    title = "Untitled"
                    properties = obj.get("properties", {})
                    if obj_type == "database":
                        title_list = obj.get("title", [])
                        if title_list:
                            title = title_list[0].get("text", {}).get("content", "Untitled")
                    else:
                        for prop_name, prop_val in properties.items():
                            if prop_val.get("type") == "title":
                                title_list = prop_val.get("title", [])
                                if title_list:
                                    title = title_list[0].get("text", {}).get("content", "Untitled")
                                    break

                    url_val = obj.get("url", f"https://notion.so/{obj_id.replace('-', '')}")
                    parent = obj.get("parent", {})
                    parent_id = parent.get("page_id") or parent.get("database_id") or parent.get("workspace_id")

                    results.append({
                        "id": obj_id,
                        "title": title,
                        "url": url_val,
                        "parent_id": parent_id,
                        "last_edited_time": obj.get("last_edited_time", ""),
                        "type": obj_type
                    })

                has_more = data.get("has_more", False)
                next_cursor = data.get("next_cursor")

            return results
        except Exception as e:
            print(f"Error discovering Notion objects: {e}")
            return []

    def fetch_database_updates(self, database_id: str, last_edited_since_iso: str) -> List[Dict[str, Any]]:
        """
        Queries a Notion database or the whole workspace for pages edited since a specific ISO timestamp.
        Returns a list of simplified message structures with full page text contents.
        If database_id is empty, None, or 'workspace'/'all', it queries all workspace pages/notes using Notion Search.
        """
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

        def parse_iso(dt_str: str) -> datetime.datetime:
            if not dt_str:
                return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
            cleaned = dt_str.replace("Z", "+00:00")
            try:
                if "." in cleaned:
                    parts = cleaned.split(".")
                    subparts = parts[1].split("+")
                    if len(subparts[0]) > 6:
                        parts[1] = subparts[0][:6] + ("+" + subparts[1] if len(subparts) > 1 else "")
                    cleaned = ".".join(parts)
                return datetime.datetime.fromisoformat(cleaned)
            except ValueError:
                return None

        since_dt = parse_iso(last_edited_since_iso)
        is_workspace_search = not database_id or database_id.strip() == "" or database_id.strip().lower() in ("workspace", "all")

        results = []

        if is_workspace_search:
            url = f"{self.base_url}/search"
            has_more = True
            next_cursor = None

            try:
                while has_more:
                    payload = {
                        "filter": {
                            "value": "page",
                            "property": "object"
                        }
                    }
                    if next_cursor:
                        payload["start_cursor"] = next_cursor

                    response = requests.post(url, json=payload, headers=self.headers, timeout=15)
                    response.raise_for_status()
                    data = response.json()

                    for page in data.get("results", []):
                        page_id = page.get("id")
                        last_edited_time = page.get("last_edited_time", "")

                        page_dt = parse_iso(last_edited_time)
                        if page_dt and since_dt:
                            if page_dt <= since_dt:
                                continue

                        title = "Untitled Page"
                        properties = page.get("properties", {})
                        for prop_name, prop_val in properties.items():
                            if prop_val.get("type") == "title":
                                title_list = prop_val.get("title", [])
                                if title_list:
                                    title = title_list[0].get("text", {}).get("content", "Untitled Page")
                                    break

                        page_body = self.fetch_page_content(page_id)
                        full_text = f"Document Title: {title}\n\n{page_body}" if page_body else f"Document Title: {title}"

                        results.append({
                            "text": full_text,
                            "user": "notion_sync_bot",
                            "channel": "notion_kb",
                            "timestamp": last_edited_time,
                            "source_id": f"notion://page/{page_id}"
                        })

                    if not has_more:
                        break

                    has_more = data.get("has_more", False)
                    next_cursor = data.get("next_cursor")

                return results
            except Exception as e:
                print(f"Error searching Notion workspace: {e}")
                return []
        else:
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
                
                for page in data.get("results", []):
                    page_id = page.get("id")
                    title = "Untitled Page"
                    properties = page.get("properties", {})
                    for prop_name, prop_val in properties.items():
                        if prop_val.get("type") == "title":
                            title_list = prop_val.get("title", [])
                            if title_list:
                                title = title_list[0].get("text", {}).get("content", "Untitled Page")
                                break
                                
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
                print(f"Error querying Notion database: {e}")
                return []

def sync_notion_metadata(tenant_id: str, api_key: str):
    """
    Discovers all pages/databases from Notion, inserts or updates them in sqlite,
    and returns a summary dict of counts.
    """
    from app.database.connection import get_tenant_connection
    client = NotionClient(api_key=api_key)
    discovered = client.discover_objects()
    
    conn = get_tenant_connection(tenant_id)
    cursor = conn.cursor()
    
    # Store every discovered item in SQLite notion_objects
    for obj in discovered:
        cursor.execute(
            """
            INSERT OR REPLACE INTO notion_objects 
            (notion_id, tenant_id, title, url, parent_id, last_edited_time, type, sync_status, last_synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                obj["id"],
                tenant_id,
                obj["title"],
                obj["url"],
                obj["parent_id"],
                obj["last_edited_time"],
                obj["type"],
                "discovered",
                datetime.datetime.utcnow().isoformat() + "Z"
            )
        )
    conn.commit()
    return len(discovered)
