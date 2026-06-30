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

class TestUnifiedSyncGraph(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.tenant_id = "tenant_unified_test"
        self.repo_dir = get_tenant_repo_dir(self.tenant_id)
        
        # Patch JWT decode
        self.patcher = patch('app.api.auth.decode_clerk_jwt')
        self.mock_decode = self.patcher.start()
        self.mock_decode.side_effect = lambda token: jwt.decode(token, "mock_secret", algorithms=["HS256"])
        
        self.cleanup()
        init_tenant_repo(self.tenant_id).close()
        
        # Populate tenant configuration
        conn = get_tenant_connection(self.tenant_id)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO tenants (id, name, created_at, git_repo_path, hnsw_index_path, config)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                self.tenant_id,
                "Unified Sync Corp",
                "2026-06-27T10:00:00Z",
                self.repo_dir,
                os.path.join(os.path.dirname(self.repo_dir), "vector_index.json"),
                json.dumps({
                    "notion": {
                        "enabled": True,
                        "database_id": "notion_db_id",
                        "api_key": "test_api_key_placeholder"
                    },
                    "slack": {
                        "enabled": True,
                        "token": "test_slack_token_placeholder",
                        "channel": "general"
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
        
        # Close database connection to release lock under Windows
        from app.database.connection import _connections
        if self.tenant_id in _connections:
            try:
                _connections[self.tenant_id].close()
                del _connections[self.tenant_id]
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

    def test_get_graph_empty(self):
        token = jwt.encode({"tenant_id": self.tenant_id, "authority_level": 0}, "mock_secret", algorithm="HS256")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = self.client.get("/v1/graph", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {})

    def test_get_graph_with_data(self):
        # Create a mock adjacency file
        tenant_dir = os.path.dirname(self.repo_dir)
        graph_dir = os.path.join(tenant_dir, "graph")
        os.makedirs(graph_dir, exist_ok=True)
        
        mock_graph = {
            "page_001": {
                "primary": ["page_002"],
                "secondary": [{"page": "page_003", "condition": "if database is postgres"}]
            }
        }
        
        with open(os.path.join(graph_dir, "adjacency.json"), "w", encoding="utf-8") as f:
            json.dump(mock_graph, f)
            
        token = jwt.encode({"tenant_id": self.tenant_id, "authority_level": 0}, "mock_secret", algorithm="HS256")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = self.client.get("/v1/graph", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), mock_graph)

    @patch('app.api.routes.run_all_sync_background')
    def test_sync_all_connectors_trigger(self, mock_all_sync):
        token = jwt.encode({"tenant_id": self.tenant_id, "authority_level": 1}, "mock_secret", algorithm="HS256")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = self.client.post("/v1/sync/all", headers=headers)
        self.assertEqual(response.status_code, 202)
        
        data = response.json()
        self.assertEqual(data["status"], "queued")
        self.assertIn("job_id", data)
        self.assertTrue(mock_all_sync.called)
        
        # Verify database record
        conn = get_tenant_connection(self.tenant_id)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (data["job_id"],))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "queued")
        self.assertEqual(row["source_type"], "document")

if __name__ == '__main__':
    unittest.main()
