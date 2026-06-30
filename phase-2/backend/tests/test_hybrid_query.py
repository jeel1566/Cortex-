import os
import sqlite3
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import json
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.models import init_database
from app.retrieval.hybrid_query import HybridQueryEngine
from app.retrieval.permissions import check_permission


class TestHybridQuery(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        init_database(self.conn)
        self.conn.execute(
            """
            INSERT INTO tenants (id, name, created_at, git_repo_path, hnsw_index_path, config)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("tenant_query_test", "Tenant Query Test", "2026-06-30T00:00:00Z", "/tmp/repo", "/tmp/index", "{}"),
        )
        self.conn.commit()
        
        self.patcher_dir = patch("app.retrieval.raw_segment_index.TENANTS_DIR", self.temp_dir.name)
        self.patcher_dir.start()

    def tearDown(self):
        self.patcher_dir.stop()
        self.conn.close()
        self.temp_dir.cleanup()

    def test_permissions_check(self):
        user_sales = {"role": "member", "clearance_level": "team", "department": "Sales"}
        user_hr = {"role": "member", "clearance_level": "confidential", "department": "HR"}
        admin = {"role": "admin"}
        
        self.assertTrue(check_permission(user_sales, "public"))
        self.assertTrue(check_permission(user_sales, "team", "Sales"))
        self.assertFalse(check_permission(user_sales, "team", "HR"))
        self.assertFalse(check_permission(user_sales, "confidential"))
        self.assertTrue(check_permission(user_hr, "confidential", "HR"))
        self.assertTrue(check_permission(admin, "restricted", "Finance"))

    @patch("app.retrieval.raw_segment_index.encode_batch")
    @patch("app.retrieval.raw_segment_index.encode")
    @patch("app.llm.embedding.encode")
    @patch("app.retrieval.hybrid_query.get_kimi_client")
    def test_query_uses_raw_segments_when_no_approved_pages_exist(self, mock_kimi, mock_query_encode, mock_idx_encode, mock_idx_batch):
        mock_idx_batch.return_value = [[0.1] * 384]
        mock_idx_encode.return_value = [0.1] * 384
        mock_query_encode.return_value = [0.1] * 384
        
        mock_client = MagicMock()
        mock_client.chat_completion.return_value = "Answer from raw segments."
        mock_kimi.return_value = mock_client

        self.conn.execute(
            """
            INSERT INTO source_objects (id, tenant_id, connector_type, external_id, object_type, title, url, author, created_at, updated_at, raw_json, content_hash, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("obj_1", "tenant_query_test", "local_upload", "upload://doc.md", "file", "Doc 1", "", "", "now", "now", "{}", "hash_doc", "{}")
        )
        self.conn.execute(
            """
            INSERT INTO source_documents (id, tenant_id, source_object_id, title, body_text, content_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("doc_1", "tenant_query_test", "obj_1", "Doc 1", "Body content", "hash_doc", "now", "now")
        )
        self.conn.execute(
            """
            INSERT INTO source_segments (id, tenant_id, document_id, segment_type, heading_path, position, text, content_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("seg_1", "tenant_query_test", "doc_1", "paragraph", "", 0, "Enterprise pricing is $10.", "hash_seg", "now")
        )
        self.conn.commit()

        engine = HybridQueryEngine(tenant_id="tenant_query_test", conn=self.conn)
        engine.raw_segment_index.add_segments([
            {"id": "seg_1", "text": "Enterprise pricing is $10.", "content_hash": "hash_seg"}
        ])

        user = {"role": "member", "clearance_level": "team", "department": "Sales"}
        res = engine.query("What is enterprise pricing?", user=user)
        
        self.assertEqual(res["answer"], "Answer from raw segments.")
        self.assertIn("segment:seg_1", res["citations"])
        self.assertEqual(len(res["pages_read"]), 0)

    @patch("app.retrieval.raw_segment_index.encode_batch")
    @patch("app.retrieval.raw_segment_index.encode")
    @patch("app.llm.embedding.encode")
    @patch("app.retrieval.hybrid_query.get_kimi_client")
    def test_unauthorized_segment_not_sent_to_llm(self, mock_kimi, mock_query_encode, mock_idx_encode, mock_idx_batch):
        mock_idx_batch.return_value = [[0.1] * 384]
        mock_idx_encode.return_value = [0.1] * 384
        mock_query_encode.return_value = [0.1] * 384
        
        mock_client = MagicMock()
        mock_kimi.return_value = mock_client

        self.conn.execute(
            """
            INSERT INTO source_objects (id, tenant_id, connector_type, external_id, object_type, title, url, author, created_at, updated_at, raw_json, content_hash, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("obj_1", "tenant_query_test", "local_upload", "upload://doc.md", "file", "Doc 1", "", "", "now", "now", "{}", "hash_doc", "{}")
        )
        self.conn.execute(
            """
            INSERT INTO source_documents (id, tenant_id, source_object_id, title, body_text, content_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("doc_1", "tenant_query_test", "obj_1", "Doc 1", "Body content", "hash_doc", "now", "now")
        )
        self.conn.execute(
            """
            INSERT INTO source_segments (id, tenant_id, document_id, segment_type, heading_path, position, text, metadata_json, content_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("seg_confidential", "tenant_query_test", "doc_1", "paragraph", "", 0, "Top secret plans.", json.dumps({"access_level": "confidential"}), "hash_seg", "now")
        )
        self.conn.commit()

        engine = HybridQueryEngine(tenant_id="tenant_query_test", conn=self.conn)
        engine.raw_segment_index.add_segments([
            {"id": "seg_confidential", "text": "Top secret plans.", "content_hash": "hash_seg"}
        ])

        user = {"role": "member", "clearance_level": "team", "department": "Sales"}
        res = engine.query("What are secret plans?", user=user)

        self.assertEqual(res["answer"], "No evidence found to answer the question.")
        self.assertNotIn("segment:seg_confidential", res["citations"])
        self.assertIn("segment:seg_confidential", res["redactions"])

    @patch("app.llm.embedding.encode")
    @patch("app.retrieval.hybrid_query.get_kimi_client")
    def test_query_caps_llm_context_for_large_approved_page(self, mock_kimi, mock_query_encode):
        mock_query_encode.return_value = [0.1] * 384

        tenant_dir = os.path.join(self.temp_dir.name, "tenant_query_test")
        repo_dir = os.path.join(tenant_dir, "repo")
        os.makedirs(repo_dir, exist_ok=True)
        page_id = "page_big"
        with open(os.path.join(repo_dir, f"{page_id}.md"), "w", encoding="utf-8") as f:
            f.write("---\nid: page_big\ntitle: Big Page\nsources: []\npropositions: []\nsynthesis_validation: {}\n---\n")
            f.write("Flowgent is a workflow automation product.\n" * 1000)

        with patch("app.config.TENANTS_DIR", self.temp_dir.name):
            engine = HybridQueryEngine(tenant_id="tenant_query_test", conn=self.conn)
        engine.tenant_dir = tenant_dir
        engine.pages_dir = repo_dir
        engine.vector_index.page_ids = [page_id]
        engine.vector_index.embeddings = [[0.1] * 384]

        mock_client = MagicMock()
        mock_client.chat_completion.return_value = "Flowgent answer."
        mock_kimi.return_value = mock_client

        res = engine.query("What is Flowgent?", user={"role": "member", "clearance_level": "team"})

        messages = mock_client.chat_completion.call_args.args[0]
        self.assertLessEqual(len(messages[1]["content"]), 4700)
        self.assertEqual(mock_client.chat_completion.call_args.kwargs["max_tokens"], 700)
        self.assertEqual(res["citations"], ["page:page_big"])


if __name__ == "__main__":
    unittest.main()
