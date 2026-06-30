import unittest
from unittest.mock import patch
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ingestion.connectors.notion import NotionAdapter


class TestNotionAdapter(unittest.TestCase):
    @patch("app.ingestion.notion.NotionClient.discover_objects")
    @patch("app.ingestion.notion.NotionClient.fetch_page_content")
    def test_notion_normalize_page_to_source_document(self, mock_fetch_content, mock_discover):
        mock_discover.return_value = [
            {
                "id": "page_123",
                "title": "Design Plan",
                "url": "https://notion.so/page_123",
                "parent_id": None,
                "last_edited_time": "2026-06-28T00:00:00Z",
                "type": "page"
            }
        ]
        mock_fetch_content.return_value = "This is page body content."

        adapter = NotionAdapter(tenant_id="tenant_test", api_key="mock_key")
        bundle = adapter.normalize()

        self.assertEqual(len(bundle.documents), 1)
        self.assertEqual(bundle.documents[0].title, "Design Plan")
        self.assertEqual(bundle.documents[0].body_text, "This is page body content.")
        self.assertEqual(bundle.objects[0].external_id, "notion://page/page_123")

    @patch("app.ingestion.notion.NotionClient.discover_objects")
    def test_notion_empty_sync_fails_without_fallback(self, mock_discover):
        mock_discover.return_value = []
        adapter = NotionAdapter(tenant_id="tenant_test", api_key="mock_key")
        with self.assertRaises(ValueError) as ctx:
            adapter.normalize()
        self.assertIn("Zero pages discovered", str(ctx.exception))

    @patch("app.ingestion.notion.NotionClient.discover_objects")
    @patch("app.ingestion.notion.NotionClient.fetch_page_content")
    def test_notion_blocks_become_source_segments(self, mock_fetch_content, mock_discover):
        mock_discover.return_value = [
            {
                "id": "page_123",
                "title": "Design Plan",
                "url": "https://notion.so/page_123",
                "parent_id": None,
                "last_edited_time": "2026-06-28T00:00:00Z",
                "type": "page"
            }
        ]
        mock_fetch_content.return_value = "# Header 1\nParagraph body text."

        adapter = NotionAdapter(tenant_id="tenant_test", api_key="mock_key")
        bundle = adapter.normalize()

        self.assertEqual(len(bundle.segments), 2)
        self.assertEqual(bundle.segments[0].segment_type, "heading")
        self.assertEqual(bundle.segments[0].text, "Header 1")
        self.assertEqual(bundle.segments[1].segment_type, "paragraph")
        self.assertEqual(bundle.segments[1].text, "Paragraph body text.")

    @patch("app.ingestion.notion.NotionClient.discover_objects")
    @patch("app.ingestion.notion.NotionClient.fetch_page_content")
    def test_notion_table_blocks_preserved(self, mock_fetch_content, mock_discover):
        mock_discover.return_value = [
            {
                "id": "page_123",
                "title": "Design Plan",
                "url": "https://notion.so/page_123",
                "parent_id": None,
                "last_edited_time": "2026-06-28T00:00:00Z",
                "type": "page"
            }
        ]
        mock_fetch_content.return_value = "| Header 1 | Header 2 |\n| Value 1 | Value 2 |"

        adapter = NotionAdapter(tenant_id="tenant_test", api_key="mock_key")
        bundle = adapter.normalize()

        self.assertEqual(len(bundle.segments), 2)
        self.assertEqual(bundle.segments[0].segment_type, "table_row")
        self.assertEqual(bundle.segments[0].text, "| Header 1 | Header 2 |")


if __name__ == "__main__":
    unittest.main()
