import os
import sys
import unittest
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import patch, MagicMock
from app.ingestion.notion import NotionClient

class TestNotionCrawler(unittest.TestCase):
    @patch.dict(os.environ, {"ALLOW_MOCK_CONNECTORS": "1"})
    def test_mock_client_discover_objects(self):
        client = NotionClient(api_key="mock_notion_key")
        discovered = client.discover_objects()
        
        self.assertEqual(len(discovered), 2)
        self.assertEqual(discovered[0]["id"], "mock_page_1")
        self.assertEqual(discovered[0]["type"], "page")
        self.assertEqual(discovered[1]["id"], "mock_db_1")
        self.assertEqual(discovered[1]["type"], "database")

    @patch("requests.get")
    def test_recursive_block_fetching(self, mock_get):
        # Setup mock API responses
        # Response for parent page
        parent_resp = MagicMock()
        parent_resp.json.return_value = {
            "results": [
                {
                    "id": "block_heading",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [{"text": {"content": "Heading Content"}}]
                    },
                    "has_children": False
                },
                {
                    "id": "block_bullet_parent",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"text": {"content": "Bullet Parent"}}]
                    },
                    "has_children": True
                }
            ]
        }
        
        # Response for nested bullet item
        child_resp = MagicMock()
        child_resp.json.return_value = {
            "results": [
                {
                    "id": "block_bullet_child",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"text": {"content": "Bullet Child"}}]
                    },
                    "has_children": False
                }
            ]
        }
        
        mock_get.side_effect = [parent_resp, child_resp]
        
        client = NotionClient(api_key="real_api_key_test")
        content = client.fetch_page_content("page_123")
        
        expected_content = "# Heading Content\n\n- Bullet Parent\n\n  - Bullet Child"
        self.assertEqual(content, expected_content)
        self.assertEqual(mock_get.call_count, 2)

    @patch("requests.get")
    def test_table_block_rendering(self, mock_get):
        # Setup mock response for table block and its table_row children
        table_resp = MagicMock()
        table_resp.json.return_value = {
            "results": [
                {
                    "id": "block_table",
                    "type": "table",
                    "table": {
                        "has_row_header": False,
                        "has_column_header": False,
                        "table_width": 2
                    },
                    "has_children": True
                }
            ]
        }
        
        rows_resp = MagicMock()
        rows_resp.json.return_value = {
            "results": [
                {
                    "id": "row_1",
                    "type": "table_row",
                    "table_row": {
                        "cells": [
                            [{"text": {"content": "Header 1"}}],
                            [{"text": {"content": "Header 2"}}]
                        ]
                    },
                    "has_children": False
                },
                {
                    "id": "row_2",
                    "type": "table_row",
                    "table_row": {
                        "cells": [
                            [{"text": {"content": "Value 1"}}],
                            [{"text": {"content": "Value 2"}}]
                        ]
                    },
                    "has_children": False
                }
            ]
        }
        
        mock_get.side_effect = [table_resp, rows_resp]
        
        client = NotionClient(api_key="real_api_key_test")
        content = client.fetch_page_content("page_with_table")
        
        expected_content = "  | Header 1 | Header 2 |\n\n  | Value 1 | Value 2 |"
        self.assertEqual(content, expected_content)
        self.assertEqual(mock_get.call_count, 2)
