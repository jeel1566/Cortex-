import os
import unittest
import jwt
import json
from fastapi.testclient import TestClient
from unittest.mock import patch

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.database.connection import get_tenant_connection

class TestSettings(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.tenant_id = "tenant_settings_test"
        
        # Patch decode_clerk_jwt to decode mock JWTs during tests
        from unittest.mock import patch
        self.patcher = patch('app.api.auth.decode_clerk_jwt')
        self.mock_decode = self.patcher.start()
        self.mock_decode.side_effect = lambda token: jwt.decode(token, "mock_secret", algorithms=["HS256"])
        
        # Setup clean config in DB
        conn = get_tenant_connection(self.tenant_id)
        cursor = conn.cursor()
        cursor.execute("UPDATE tenants SET config = ? WHERE id = ?", (json.dumps({"ai_provider": "not_configured"}), self.tenant_id))
        conn.commit()

    def tearDown(self):
        self.patcher.stop()

    def test_settings_get_default(self):
        token = jwt.encode({"tenant_id": self.tenant_id, "authority_level": 1}, "mock_secret", algorithm="HS256")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = self.client.get("/v1/settings", headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["ai_provider"], "not_configured")
        self.assertIn("config", data)
        self.assertIn("connectors", data)
        self.assertFalse(data["connectors"]["notion"]["enabled"])
        self.assertEqual(data["connectors"]["notion"]["api_key"], "")

    def test_settings_post_and_masking(self):
        token = jwt.encode({"tenant_id": self.tenant_id, "authority_level": 1}, "mock_secret", algorithm="HS256")
        headers = {"Authorization": f"Bearer {token}"}
        
        payload = {
            "ai_provider": "web_api",
            "config": {
                "web_api_endpoint": "https://api.openai.com/v1",
                "web_api_key": "super_secret_openai_key",
                "web_api_model": "gpt-4"
            },
            "connectors": {
                "notion": {
                    "enabled": True,
                    "database_id": "notion_db_123",
                    "api_key": "super_secret_notion_key"
                },
                "slack": {
                    "enabled": False,
                    "token": "",
                    "channel": ""
                }
              }
        }
        
        # Save Settings
        response = self.client.post("/v1/settings", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        
        # Check GET masks values
        response = self.client.get("/v1/settings", headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["ai_provider"], "web_api")
        self.assertEqual(data["config"]["web_api_key"], "********")
        self.assertEqual(data["connectors"]["notion"]["api_key"], "********")
        self.assertEqual(data["connectors"]["notion"]["database_id"], "notion_db_123")
        
        # Submit update with masked placeholders (simulating UI update)
        payload["config"]["web_api_key"] = "********"
        payload["connectors"]["notion"]["api_key"] = "********"
        payload["connectors"]["notion"]["database_id"] = "updated_notion_db"
        
        response = self.client.post("/v1/settings", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        
        # Check database still has the original secrets
        conn = get_tenant_connection(self.tenant_id)
        cursor = conn.cursor()
        cursor.execute("SELECT config FROM tenants WHERE id = ?", (self.tenant_id,))
        row = cursor.fetchone()
        config = json.loads(row["config"])
        
        self.assertEqual(config["ai_provider_config"]["web_api_key"], "super_secret_openai_key")
        self.assertEqual(config["notion"]["api_key"], "super_secret_notion_key")
        self.assertEqual(config["notion"]["database_id"], "updated_notion_db")

    def test_connector_sync_without_real_key_fails_loudly(self):
        token = jwt.encode({"tenant_id": self.tenant_id, "authority_level": 1}, "mock_secret", algorithm="HS256")
        headers = {"Authorization": f"Bearer {token}"}

        with patch.dict(os.environ, {"NOTION_API_KEY": "", "ALLOW_MOCK_CONNECTORS": ""}, clear=False):
            response = self.client.post("/v1/connectors/notion/sync", headers=headers)

        self.assertEqual(response.status_code, 202)
        job_id = response.json()["job_id"]

        conn = get_tenant_connection(self.tenant_id)
        row = conn.execute("SELECT status, error_message FROM sync_runs WHERE id = ?", (job_id,)).fetchone()
        self.assertEqual(row["status"], "failed")
        self.assertIn("NOTION_API_KEY is not configured", row["error_message"])

if __name__ == '__main__':
    unittest.main()
