import unittest
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import patch
from app.ingestion.connectors.slack import SlackAdapter
from app.ingestion.connectors.google_docs import GoogleDocsAdapter


class TestSlackGoogleAdapters(unittest.TestCase):
    @patch.dict(os.environ, {"ALLOW_MOCK_CONNECTORS": "1"})
    def test_slack_thread_becomes_document(self):
        adapter = SlackAdapter(tenant_id="tenant_test", client_token="mock_slack_token", channels=["C123"])
        bundle = adapter.normalize()
        
        self.assertEqual(len(bundle.documents), 1)
        self.assertEqual(bundle.documents[0].source_object_external_id, "slack://channel/C123/thread/1719583200.0001")
        self.assertEqual(bundle.documents[0].title, "Parent thread message")

    @patch.dict(os.environ, {"ALLOW_MOCK_CONNECTORS": "1"})
    def test_slack_messages_become_ordered_segments(self):
        adapter = SlackAdapter(tenant_id="tenant_test", client_token="mock_slack_token", channels=["C123"])
        bundle = adapter.normalize()
        
        self.assertEqual(len(bundle.segments), 2)
        self.assertEqual(bundle.segments[0].segment_type, "message")
        self.assertEqual(bundle.segments[0].text, "Parent thread message")
        self.assertEqual(bundle.segments[0].position, 0)
        self.assertEqual(bundle.segments[1].text, "First reply message")
        self.assertEqual(bundle.segments[1].position, 1)

    @patch.dict(os.environ, {"ALLOW_MOCK_CONNECTORS": "1"})
    def test_google_doc_headings_become_heading_paths(self):
        adapter = GoogleDocsAdapter(tenant_id="tenant_test", doc_id="doc_123", credentials_token="mock_gdocs_token")
        bundle = adapter.normalize()
        
        self.assertEqual(len(bundle.documents), 1)
        self.assertEqual(bundle.segments[1].segment_type, "heading")
        self.assertEqual(bundle.segments[1].text, "Introduction")
        self.assertEqual(bundle.segments[2].heading_path, ["Introduction"])

    @patch.dict(os.environ, {"ALLOW_MOCK_CONNECTORS": "1"})
    def test_google_doc_table_rows_preserved(self):
        adapter = GoogleDocsAdapter(tenant_id="tenant_test", doc_id="doc_123", credentials_token="mock_gdocs_token")
        bundle = adapter.normalize()
        
        table_rows = [s for s in bundle.segments if s.segment_type == "table_row"]
        self.assertEqual(len(table_rows), 2)
        self.assertEqual(table_rows[0].text, "Metric Name | Value")
        self.assertEqual(table_rows[1].text, "Target NPS | 75")


if __name__ == "__main__":
    unittest.main()
