import os
import sqlite3
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.models import init_database
from app.retrieval.permissions import check_permission
from app.retrieval.hybrid_query import HybridQueryEngine


class TestNewEnginePermissions(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        init_database(self.conn)
        self.conn.execute(
            """
            INSERT INTO tenants (id, name, created_at, git_repo_path, hnsw_index_path, config)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("tenant_permissions_test", "Tenant Perms Test", "2026-06-30T00:00:00Z", "/tmp/repo", "/tmp/index", "{}"),
        )
        self.conn.commit()

        self.patcher_dir = patch("app.config.TENANTS_DIR", self.temp_dir.name)
        self.patcher_dir.start()

    def tearDown(self):
        self.patcher_dir.stop()
        self.conn.close()
        self.temp_dir.cleanup()

    def test_clearance_matrix(self):
        users = {
            "public_user": {"role": "member", "clearance_level": "public", "department": "Engineering"},
            "team_user": {"role": "member", "clearance_level": "team", "department": "Engineering"},
            "conf_user": {"role": "member", "clearance_level": "confidential", "department": "Engineering"},
            "restricted_user": {"role": "member", "clearance_level": "restricted", "department": "Engineering"},
            "admin_user": {"role": "admin", "clearance_level": "public", "department": "Finance"},
        }
        
        self.assertTrue(check_permission(users["public_user"], "public"))
        self.assertTrue(check_permission(users["team_user"], "public"))
        self.assertTrue(check_permission(users["conf_user"], "public"))
        self.assertTrue(check_permission(users["restricted_user"], "public"))
        self.assertTrue(check_permission(users["admin_user"], "public"))

        self.assertFalse(check_permission(users["public_user"], "team"))
        self.assertTrue(check_permission(users["team_user"], "team"))
        self.assertTrue(check_permission(users["conf_user"], "team"))
        self.assertTrue(check_permission(users["restricted_user"], "team"))
        self.assertTrue(check_permission(users["admin_user"], "team"))

        self.assertFalse(check_permission(users["public_user"], "confidential"))
        self.assertFalse(check_permission(users["team_user"], "confidential"))
        self.assertTrue(check_permission(users["conf_user"], "confidential"))
        self.assertTrue(check_permission(users["restricted_user"], "confidential"))
        self.assertTrue(check_permission(users["admin_user"], "confidential"))

        self.assertFalse(check_permission(users["public_user"], "restricted"))
        self.assertFalse(check_permission(users["team_user"], "restricted"))
        self.assertFalse(check_permission(users["conf_user"], "restricted"))
        self.assertTrue(check_permission(users["restricted_user"], "restricted"))
        self.assertTrue(check_permission(users["admin_user"], "restricted"))

    def test_department_scenarios(self):
        user_sales = {"role": "member", "clearance_level": "team", "department": "Sales"}
        user_eng = {"role": "member", "clearance_level": "team", "department": "Engineering"}
        
        self.assertTrue(check_permission(user_sales, "team", "Sales"))
        self.assertFalse(check_permission(user_sales, "team", "Engineering"))
        
        self.assertTrue(check_permission(user_eng, "team", "Engineering"))
        self.assertFalse(check_permission(user_eng, "team", "Sales"))


if __name__ == "__main__":
    unittest.main()
