import os
import shutil
import unittest
import jwt
from fastapi.testclient import TestClient

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.storage.git_store import get_tenant_repo_dir, init_tenant_repo
from app.database.connection import get_tenant_connection

class TestAuthIsolation(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.tenant_a = "tenant_a"
        self.tenant_b = "tenant_b"
        self.repo_a = get_tenant_repo_dir(self.tenant_a)
        self.repo_b = get_tenant_repo_dir(self.tenant_b)
        
        # Clean directories
        self.cleanup()
        
        # Initialize tenant repos
        init_tenant_repo(self.tenant_a).close()
        init_tenant_repo(self.tenant_b).close()

    def tearDown(self):
        self.cleanup()
        
    def cleanup(self):
        import gc
        gc.collect()
        
        def onerror(func, path, exc_info):
            import stat
            os.chmod(path, stat.S_IWRITE)
            func(path)
            
        for t in [self.tenant_a, self.tenant_b]:
            p = os.path.dirname(get_tenant_repo_dir(t))
            if os.path.exists(p):
                try:
                    shutil.rmtree(p, onerror=onerror)
                except Exception:
                    pass

    def test_unauthorized_access(self):
        # Access query endpoint without token -> 403 (due to HTTPBearer header check)
        response = self.client.post("/v1/query", json={"question": "hello"})
        self.assertEqual(response.status_code, 403)

    def test_insufficient_authority_ingest(self):
        # Ingest requires min level 2. User has level 1.
        token = jwt.encode({"tenant_id": self.tenant_a, "authority_level": 1}, "mock_secret", algorithm="HS256")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = self.client.post(
            "/v1/ingest", 
            json={"source_type": "slack", "content": "raw content"}, 
            headers=headers
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Insufficient authority level", response.json()["detail"])

    def test_sensitivity_redaction_l1_vs_l3(self):
        # Create a page with sensitive claims under tenant A
        page_content = """---
id: page_001
title: Test Security
version: 1
last_updated: 2026-06-17T10:00:00Z
access_level: team
primary_links: []
secondary_links: []
sources: []
propositions:
  - id: prop_1
    text: "Claim 1 is public."
    sensitivity: public
  - id: prop_2
    text: "Claim 2 is team policy."
    sensitivity: team
  - id: prop_3
    text: "Claim 3 is highly confidential."
    sensitivity: confidential
---
# Test Security
"""
        with open(os.path.join(self.repo_a, "page_001.md"), "w", encoding="utf-8") as f:
            f.write(page_content)
            
        # 1. Fetch with L1 (Team member) -> should redact L3 (confidential) claims
        token_l1 = jwt.encode({"tenant_id": self.tenant_a, "authority_level": 1}, "mock_secret", algorithm="HS256")
        headers_l1 = {"Authorization": f"Bearer {token_l1}"}
        
        response_l1 = self.client.get("/v1/page/page_001", headers=headers_l1)
        self.assertEqual(response_l1.status_code, 200)
        props_l1 = response_l1.json()["propositions"]
        
        # Verify L1 sees public and team claims, but L3 is redacted
        self.assertEqual(props_l1[0]["text"], "Claim 1 is public.")
        self.assertEqual(props_l1[1]["text"], "Claim 2 is team policy.")
        self.assertEqual(props_l1[2]["text"], "[REDACTED - INSUFFICIENT CLEARANCE]")

        # 2. Fetch with L3 (Moderator/Manager) -> should see all claims
        token_l3 = jwt.encode({"tenant_id": self.tenant_a, "authority_level": 3}, "mock_secret", algorithm="HS256")
        headers_l3 = {"Authorization": f"Bearer {token_l3}"}
        
        response_l3 = self.client.get("/v1/page/page_001", headers=headers_l3)
        self.assertEqual(response_l3.status_code, 200)
        props_l3 = response_l3.json()["propositions"]
        self.assertEqual(props_l3[2]["text"], "Claim 3 is highly confidential.")

    def test_tenant_isolation(self):
        # Create a page in tenant A repo only
        with open(os.path.join(self.repo_a, "page_a.md"), "w", encoding="utf-8") as f:
            f.write("---\nid: page_a\ntitle: Tenant A Page\n---\nBody A")
            
        # Fetch using tenant A credentials -> 200
        token_a = jwt.encode({"tenant_id": self.tenant_a, "authority_level": 1}, "mock_secret", algorithm="HS256")
        response_a = self.client.get("/v1/page/page_a", headers={"Authorization": f"Bearer {token_a}"})
        self.assertEqual(response_a.status_code, 200)
        
        # Fetch using tenant B credentials -> should fail with 404 (because page doesn't exist in tenant B directory)
        token_b = jwt.encode({"tenant_id": self.tenant_b, "authority_level": 1}, "mock_secret", algorithm="HS256")
        response_b = self.client.get("/v1/page/page_a", headers={"Authorization": f"Bearer {token_b}"})
        self.assertEqual(response_b.status_code, 404)

if __name__ == '__main__':
    unittest.main()
