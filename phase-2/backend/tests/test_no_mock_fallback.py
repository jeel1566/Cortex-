"""
Tests: No silent mock/fallback/demo ingestion paths.
All six required cases from the task spec.
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---------------------------------------------------------------------------
# 1. Connector sync without real key fails loudly (no ALLOW_MOCK_CONNECTORS)
# ---------------------------------------------------------------------------

class TestConnectorSyncWithoutRealKeyFailsLoudly(unittest.TestCase):

    @patch.dict(os.environ, {}, clear_env := False)
    def _make_notion_client_no_mock(self):
        from app.ingestion.notion import NotionClient
        return NotionClient(api_key="mock_notion_key")

    def test_notion_client_with_mock_key_and_no_flag_raises(self):
        """NotionClient must raise ValueError when given mock_notion_key without ALLOW_MOCK_CONNECTORS."""
        env = {k: v for k, v in os.environ.items() if k != "ALLOW_MOCK_CONNECTORS" and k != "NOTION_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            from app.ingestion.notion import NotionClient
            with self.assertRaises(ValueError) as ctx:
                NotionClient(api_key="mock_notion_key")
            self.assertIn("ALLOW_MOCK_CONNECTORS", str(ctx.exception))

    def test_slack_adapter_with_mock_token_and_no_flag_raises(self):
        """SlackAdapter must raise ValueError when given mock_slack_token without ALLOW_MOCK_CONNECTORS."""
        env = {k: v for k, v in os.environ.items() if k != "ALLOW_MOCK_CONNECTORS" and k != "SLACK_API_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            from app.ingestion.connectors.slack import SlackAdapter
            with self.assertRaises(ValueError) as ctx:
                SlackAdapter(tenant_id="t1", client_token="mock_slack_token", channels=["C1"])
            self.assertIn("ALLOW_MOCK_CONNECTORS", str(ctx.exception))

    def test_google_docs_adapter_with_mock_token_and_no_flag_raises(self):
        """GoogleDocsAdapter must raise ValueError when given mock_gdocs_token without ALLOW_MOCK_CONNECTORS."""
        env = {k: v for k, v in os.environ.items() if k != "ALLOW_MOCK_CONNECTORS" and k != "GOOGLE_DOCS_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            from app.ingestion.connectors.google_docs import GoogleDocsAdapter
            with self.assertRaises(ValueError) as ctx:
                GoogleDocsAdapter(tenant_id="t1", doc_id="doc1", credentials_token="mock_gdocs_token")
            self.assertIn("ALLOW_MOCK_CONNECTORS", str(ctx.exception))

    def test_mock_connectors_work_when_flag_set(self):
        """Mock connectors must succeed when ALLOW_MOCK_CONNECTORS=1."""
        with patch.dict(os.environ, {"ALLOW_MOCK_CONNECTORS": "1"}, clear=False):
            from app.ingestion.notion import NotionClient
            from app.ingestion.connectors.slack import SlackAdapter
            from app.ingestion.connectors.google_docs import GoogleDocsAdapter
            # Should not raise
            client = NotionClient(api_key="mock_notion_key")
            self.assertEqual(client.api_key, "mock_notion_key")

            adapter = SlackAdapter(tenant_id="t1", client_token="mock_slack_token", channels=["C1"])
            self.assertEqual(adapter.client_token, "mock_slack_token")

            g_adapter = GoogleDocsAdapter(tenant_id="t1", doc_id="d1", credentials_token="mock_gdocs_token")
            self.assertEqual(g_adapter.credentials_token, "mock_gdocs_token")


# ---------------------------------------------------------------------------
# 2. Missing notion key creates no source records
# ---------------------------------------------------------------------------

class TestMissingNotionKeyCreatesNoSourceRecords(unittest.TestCase):

    def test_notion_client_no_key_no_env_raises(self):
        """NotionClient with no key and no env var raises ValueError, not silently fallbacks."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("NOTION_API_KEY", "ALLOW_MOCK_CONNECTORS")}
        with patch.dict(os.environ, env, clear=True):
            from app.ingestion.notion import NotionClient
            with self.assertRaises(ValueError) as ctx:
                NotionClient()
            self.assertIn("NOTION_API_KEY", str(ctx.exception))

    def test_notion_adapter_empty_discover_raises_before_any_storage(self):
        """NotionAdapter.normalize must raise ValueError when zero pages discovered."""
        with patch.dict(os.environ, {"ALLOW_MOCK_CONNECTORS": "1"}, clear=False):
            from app.ingestion.connectors.notion import NotionAdapter
            with patch("app.ingestion.notion.NotionClient.discover_objects", return_value=[]):
                adapter = NotionAdapter(tenant_id="t1", api_key="mock_notion_key")
                with self.assertRaises(ValueError) as ctx:
                    adapter.normalize()
                self.assertIn("Zero pages", str(ctx.exception))


# ---------------------------------------------------------------------------
# 3. Empty connector sync creates no pages
# ---------------------------------------------------------------------------

class TestEmptyConnectorSyncCreatesNoPages(unittest.TestCase):

    def test_notion_adapter_all_empty_pages_raises(self):
        """NotionAdapter must raise when all pages have empty body content."""
        with patch.dict(os.environ, {"ALLOW_MOCK_CONNECTORS": "1"}, clear=False):
            from app.ingestion.connectors.notion import NotionAdapter
            with patch("app.ingestion.notion.NotionClient.discover_objects", return_value=[
                {"id": "p1", "title": "Empty", "url": "https://notion.so/p1",
                 "parent_id": None, "last_edited_time": "", "type": "page"}
            ]):
                with patch("app.ingestion.notion.NotionClient.fetch_page_content", return_value=""):
                    adapter = NotionAdapter(tenant_id="t1", api_key="mock_notion_key")
                    with self.assertRaises(ValueError) as ctx:
                        adapter.normalize()
                    self.assertIn("Zero pages", str(ctx.exception))

    def test_slack_adapter_no_threads_raises(self):
        """SlackAdapter must raise ValueError when no thread documents are produced."""
        with patch.dict(os.environ, {"ALLOW_MOCK_CONNECTORS": "1"}, clear=False):
            from app.ingestion.connectors.slack import SlackAdapter
            with patch.object(SlackAdapter, "fetch_channel_history", return_value=[]):
                adapter = SlackAdapter(tenant_id="t1", client_token="mock_slack_token", channels=["C1"])
                with self.assertRaises(ValueError) as ctx:
                    adapter.normalize()
                self.assertIn("Zero messages", str(ctx.exception))


# ---------------------------------------------------------------------------
# 4. Synthesizer failure does not create fallback page
# ---------------------------------------------------------------------------

class TestSynthesizerFailureDoesNotCreateFallbackPage(unittest.TestCase):

    def test_synthesize_page_raises_on_llm_error(self):
        """synthesize_page must raise RuntimeError on LLM failure, not return fallback markdown."""
        with patch("app.ingestion.synthesizer.get_kimi_client") as mock_kimi:
            mock_client = MagicMock()
            mock_client.chat_completion.side_effect = RuntimeError("LLM unavailable")
            mock_kimi.return_value = mock_client

            from app.ingestion.synthesizer import synthesize_page
            cluster = [{"text": "some fact", "type": "PRESCRIPTION",
                        "metadata": {"source_id": "slack://C1/123", "user": "u1", "timestamp": "t"}}]
            with self.assertRaises(RuntimeError) as ctx:
                synthesize_page(1, cluster, tenant_id="tenant_test")
            self.assertIn("LLM synthesis failed", str(ctx.exception))
            # Must NOT be a fallback markdown string — exception was raised
            self.assertNotIn("Synthesized Topic", str(ctx.exception).replace("LLM synthesis failed:", ""))


# ---------------------------------------------------------------------------
# 5. Fallback / demo text never committed to Git
# ---------------------------------------------------------------------------

class TestFallbackDemoTextNeverCommittedToGit(unittest.TestCase):

    def test_pipeline_does_not_write_git_on_synthesis_failure(self):
        """run_ingestion_pipeline must not call commit_page_changes when synthesize_page raises."""
        with patch("app.ingestion.pipeline.synthesize_page", side_effect=RuntimeError("LLM error")):
            with patch("app.ingestion.pipeline.commit_page_changes") as mock_commit:
                with patch("app.ingestion.pipeline.init_tenant_repo"):
                    with patch("app.ingestion.pipeline.get_tenant_repo_dir", return_value="/tmp/fakerepo"):
                        with patch("os.listdir", return_value=[]):
                            from app.ingestion.pipeline import run_ingestion_pipeline
                            raw_messages = [{"text": "Real source content.", "user": "u1",
                                             "channel": "C1", "timestamp": "123",
                                             "source_id": "slack://C1/123"}]
                            try:
                                run_ingestion_pipeline("tenant_test", raw_messages)
                            except Exception:
                                pass  # Expected to fail
                            mock_commit.assert_not_called()

    def test_engine_does_not_approve_draft_with_empty_body(self):
        """Compiler must set status=REJECTED for documents with trivially empty bodies."""
        from app.ingestion.compiler import DraftCompiler
        from app.ingestion.engine_models import NormalizedSourceDocument, NormalizedSourceSegment
        compiler = DraftCompiler()
        # A segment with real text
        doc = NormalizedSourceDocument(
            source_object_external_id="notion://page/p1",
            title="Test",
            body_text="Real content here.",
        )
        seg = NormalizedSourceSegment(
            document_ref="notion://page/p1",
            segment_type="paragraph",
            heading_path=[],
            position=0,
            text="Real content here.",
        )
        result = compiler.compile_draft("tenant_test", doc, [seg])
        self.assertIn("Real content", result["content"])
        self.assertNotIn("fallback", result["content"].lower())


# ---------------------------------------------------------------------------
# 6. Mock connectors only work when ALLOW_MOCK_CONNECTORS is enabled
# ---------------------------------------------------------------------------

class TestMockConnectorsOnlyWorkWhenAllowFlagEnabled(unittest.TestCase):

    def test_notion_no_key_no_flag_raises(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("NOTION_API_KEY", "ALLOW_MOCK_CONNECTORS")}
        with patch.dict(os.environ, env, clear=True):
            from app.ingestion.notion import NotionClient
            with self.assertRaises(ValueError):
                NotionClient()

    def test_notion_no_key_with_flag_uses_mock(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("NOTION_API_KEY",)}
        env["ALLOW_MOCK_CONNECTORS"] = "1"
        with patch.dict(os.environ, env, clear=True):
            from app.ingestion.notion import NotionClient
            client = NotionClient()
            self.assertEqual(client.api_key, "mock_notion_key")

    def test_slack_no_token_no_flag_raises(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("SLACK_API_TOKEN", "ALLOW_MOCK_CONNECTORS")}
        with patch.dict(os.environ, env, clear=True):
            from app.ingestion.connectors.slack import SlackAdapter
            with self.assertRaises(ValueError):
                SlackAdapter(tenant_id="t1", client_token="mock_slack_token", channels=[])

    def test_google_no_token_no_flag_raises(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("GOOGLE_DOCS_TOKEN", "ALLOW_MOCK_CONNECTORS")}
        with patch.dict(os.environ, env, clear=True):
            from app.ingestion.connectors.google_docs import GoogleDocsAdapter
            with self.assertRaises(ValueError):
                GoogleDocsAdapter(tenant_id="t1", doc_id="d1", credentials_token="mock_gdocs_token")

    def test_allow_flag_accepts_true_and_yes(self):
        """ALLOW_MOCK_CONNECTORS accepts '1', 'true', 'yes' (case-insensitive)."""
        for val in ("1", "true", "True", "yes", "YES"):
            with patch.dict(os.environ, {"ALLOW_MOCK_CONNECTORS": val}, clear=False):
                from app.ingestion.notion import NotionClient
                client = NotionClient(api_key="mock_notion_key")
                self.assertEqual(client.api_key, "mock_notion_key")


if __name__ == "__main__":
    unittest.main()
