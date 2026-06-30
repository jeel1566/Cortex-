import os
import shutil
import unittest
import jwt
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.storage.git_store import get_tenant_repo_dir, init_tenant_repo
from app.database.connection import get_tenant_connection
from app.ingestion.notion import NotionClient
from app.ingestion.queue import IngestionQueueWorker

class TestNotionFeedback(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.tenant_id = "tenant_notion_test"
        self.repo_dir = get_tenant_repo_dir(self.tenant_id)
        
        # Patch decode_clerk_jwt to decode mock JWTs during tests
        from unittest.mock import patch
        self.patcher = patch('app.api.auth.decode_clerk_jwt')
        self.mock_decode = self.patcher.start()
        self.mock_decode.side_effect = lambda token: jwt.decode(token, "mock_secret", algorithms=["HS256"])
        
        self.cleanup()
        init_tenant_repo(self.tenant_id).close()
        
        # Populate tenant config in metadata SQLite
        conn = get_tenant_connection(self.tenant_id)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO tenants (id, name, created_at, git_repo_path, hnsw_index_path, config)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                self.tenant_id,
                "Notion Test Co",
                "2026-06-17T10:00:00Z",
                self.repo_dir,
                os.path.join(os.path.dirname(self.repo_dir), "vector_index.json"),
                json.dumps({
                    "notion": {
                        "enabled": True,
                        "database_id": "db_123",
                        "last_polled": "2026-06-17T00:00:00Z"
                    }
                })
            )
        )
        conn.commit()

    def tearDown(self):
        self.patcher.stop()
        self.cleanup()
        
    def cleanup(self):
        import gc
        gc.collect()
        
        # Delete tenant from database
        try:
            conn = get_tenant_connection(self.tenant_id)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tenants WHERE id = ?", (self.tenant_id,))
            conn.commit()
        except Exception:
            pass

        def onerror(func, path, exc_info):
            import stat
            os.chmod(path, stat.S_IWRITE)
            func(path)
            
        p = os.path.dirname(self.repo_dir)
        if os.path.exists(p):
            try:
                shutil.rmtree(p, onerror=onerror)
            except Exception:
                pass

    @patch.dict(os.environ, {"ALLOW_MOCK_CONNECTORS": "1"})
    def test_notion_client_mock_retrieval(self):
        client = NotionClient(api_key="mock_notion_key")
        updates = client.fetch_database_updates("db_123", "2026-06-17T00:00:00Z")
        self.assertEqual(len(updates), 1)
        self.assertIn("Superset", updates[0]["text"])
        self.assertEqual(updates[0]["source_id"], "notion://page/mock_page_1")

    @patch.dict(os.environ, {"ALLOW_MOCK_CONNECTORS": "1"})
    @patch('app.ingestion.queue.run_ingestion_pipeline')
    def test_queue_worker_polls_and_syncs(self, mock_pipeline):
        worker = IngestionQueueWorker(poll_interval_sec=1)
        worker.poll_all_tenants()
        
        # Verify that the ingestion pipeline was triggered with mock Notion updates
        self.assertTrue(mock_pipeline.called)
        args, kwargs = mock_pipeline.call_args
        self.assertEqual(args[0], self.tenant_id)
        self.assertEqual(args[1][0]["source_id"], "notion://page/mock_page_1")

    @patch('app.api.routes.run_background_ingest')
    def test_feedback_triggers_resynthesis(self, mock_bg_ingest):
        token = jwt.encode({"tenant_id": self.tenant_id, "authority_level": 1}, "mock_secret", algorithm="HS256")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Submit feedback with correction and affected pages
        feedback_payload = {
            "query_id": "q_123",
            "feedback_type": "wrong_answer",
            "affected_pages": ["page_001"],
            "correct_answer": "Refund window is now 60 days."
        }
        
        response = self.client.post("/v1/feedback", json=feedback_payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertTrue(data["resynthesis_queued"])
        self.assertEqual(data["pages_flagged"], ["page_001"])
        
        # Verify that the background task was dispatched
        self.assertTrue(mock_bg_ingest.called)
        
        # Check SQLite DB to confirm feedback recorded
        conn = get_tenant_connection(self.tenant_id)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM feedback WHERE query_id = 'q_123'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["feedback_type"], "wrong_answer")
        self.assertEqual(row["correct_answer"], "Refund window is now 60 days.")

if __name__ == '__main__':
    unittest.main()
