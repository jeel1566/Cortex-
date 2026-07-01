import os
import json
import sqlite3
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.models import init_database
from app.ingestion.connectors.local_upload import LocalUploadAdapter
from app.ingestion.engine import CortexNewEngine
from app.retrieval.hybrid_query import HybridQueryEngine
from app.retrieval.raw_segment_index import RawSegmentIndex


class TestNewEngineEndToEnd(unittest.TestCase):
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
            ("tenant_e2e_test", "Tenant E2E Test", "2026-06-30T00:00:00Z", "/tmp/repo", "/tmp/index", "{}"),
        )
        self.conn.commit()

        self.patcher_dir = patch("app.config.TENANTS_DIR", self.temp_dir.name)
        self.patcher_dir.start()

    def tearDown(self):
        self.patcher_dir.stop()
        self.conn.close()
        self.temp_dir.cleanup()

    def dummy_encode_batch(self, texts):
        return [[float(i) / 384.0] * 384 for i in range(len(texts))]

    def dummy_encode(self, text):
        return [0.1] * 384

    @patch("app.retrieval.raw_segment_index.encode_batch")
    @patch("app.retrieval.raw_segment_index.encode")
    @patch("app.llm.embedding.encode")
    @patch("app.retrieval.hybrid_query.get_kimi_client")
    @patch("app.ingestion.compiler.get_kimi_client")
    @patch("app.storage.git_store.init_tenant_repo")
    @patch("app.storage.git_store.get_tenant_repo_dir")
    @patch("app.storage.git_store.commit_page_changes")
    def test_e2e_local_upload_pipeline_flow(self, mock_commit, mock_get_repo_dir, mock_init_repo, mock_compiler_kimi, mock_kimi, mock_query_encode, mock_idx_encode, mock_idx_batch):
        mock_idx_batch.side_effect = self.dummy_encode_batch
        mock_idx_encode.side_effect = self.dummy_encode
        mock_query_encode.side_effect = self.dummy_encode

        # Compiler LLM returns structured JSON
        _llm_json = json.dumps({
            "title": "Gunicorn Setup",
            "summary": "Deploy Gunicorn behind Nginx.",
            "sections": [{"heading": "Setup", "body": "Deploy Gunicorn behind Nginx reversed proxy.", "evidence_segment_ids": ["srcseg_x"]}],
            "propositions": [{"text": "Gunicorn runs behind Nginx.", "evidence_segment_ids": ["srcseg_x"], "source_quotes": ["Nginx reversed proxy"], "confidence": 0.9, "sensitivity": "team"}],
            "suggested_links": [],
            "knowledge_gaps": [],
        })
        mock_compiler_client = MagicMock()
        mock_compiler_client.chat_completion.return_value = _llm_json
        mock_compiler_kimi.return_value = mock_compiler_client

        mock_client = MagicMock()
        mock_client.chat_completion.return_value = "Mocked LLM Answer based on Gunicorn setup guide."
        mock_kimi.return_value = mock_client
        
        repo_dir = os.path.join(self.temp_dir.name, "tenant_e2e_test", "repo")
        os.makedirs(repo_dir, exist_ok=True)
        mock_get_repo_dir.return_value = repo_dir
        mock_commit.return_value = "commit_1234abcd"

        file_path = os.path.join(self.temp_dir.name, "setup.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("# Gunicorn Setup\nDeploy Gunicorn behind Nginx reversed proxy.")

        adapter = LocalUploadAdapter(tenant_id="tenant_e2e_test", file_path=file_path)
        bundle = adapter.normalize()
        self.assertEqual(len(bundle.documents), 1)
        self.assertEqual(len(bundle.segments), 2)

        engine = CortexNewEngine(conn=self.conn)
        ingest_res = engine.ingest_bundle("tenant_e2e_test", bundle)
        self.assertTrue(ingest_res.ok)
        self.assertEqual(ingest_res.counts["objects"], 1)
        self.assertEqual(ingest_res.counts["drafts"], 1)

        segs = self.conn.execute("SELECT id, text, content_hash FROM source_segments WHERE tenant_id = 'tenant_e2e_test'").fetchall()
        engine_segs = [dict(r) for r in segs]
        idx = RawSegmentIndex("tenant_e2e_test")
        idx.add_segments(engine_segs)

        draft_row = self.conn.execute("SELECT * FROM knowledge_page_drafts WHERE status = 'DRAFT'").fetchone()
        self.assertIsNotNone(draft_row)
        draft_id = draft_row["id"]

        app_res = engine.approve_draft("tenant_e2e_test", draft_id, "admin_approver")
        self.assertTrue(app_res.ok)
        self.assertEqual(app_res.commit_sha, "commit_1234abcd")

        query_engine = HybridQueryEngine(tenant_id="tenant_e2e_test", conn=self.conn)
        user = {"role": "member", "clearance_level": "team", "department": "Engineering"}
        
        query_res = query_engine.query("How to set up Gunicorn?", user=user)

        self.assertEqual(query_res["answer"], "Mocked LLM Answer based on Gunicorn setup guide.")
        self.assertIn(f"page:{app_res.page_id}", query_res["citations"])


if __name__ == "__main__":
    unittest.main()
