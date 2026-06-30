import os
import sqlite3
import sys
import unittest
import unittest.mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.models import init_database
from app.ingestion.engine import CortexNewEngine
from app.ingestion.engine_models import (
    NormalizedSourceBundle,
    NormalizedSourceDocument,
    NormalizedSourceObject,
    NormalizedSourceSegment,
)


class TestCortexNewEngine(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        init_database(self.conn)
        self.conn.execute(
            """
            INSERT INTO tenants (id, name, created_at, git_repo_path, hnsw_index_path, config)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("tenant_engine_test", "Tenant Engine Test", "2026-06-30T00:00:00Z", "/tmp/repo", "/tmp/index", "{}"),
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def bundle(self):
        return NormalizedSourceBundle(
            tenant_id="tenant_engine_test",
            connector_type="local_upload",
            objects=[
                NormalizedSourceObject(
                    tenant_id="tenant_engine_test",
                    connector_type="local_upload",
                    external_id="upload://handbook.md",
                    object_type="file",
                    title="Handbook",
                )
            ],
            documents=[
                NormalizedSourceDocument(
                    source_object_external_id="upload://handbook.md",
                    title="Handbook",
                    body_text="# Handbook\nRemote work is allowed.",
                )
            ],
            segments=[
                NormalizedSourceSegment(
                    document_ref="upload://handbook.md",
                    segment_type="heading",
                    heading_path=["Handbook"],
                    position=0,
                    text="Handbook",
                ),
                NormalizedSourceSegment(
                    document_ref="upload://handbook.md",
                    segment_type="paragraph",
                    heading_path=["Handbook"],
                    position=1,
                    text="Remote work is allowed.",
                ),
            ],
        )

    def test_engine_ingest_does_not_commit_to_git(self):
        result = CortexNewEngine(conn=self.conn).ingest_bundle("tenant_engine_test", self.bundle())

        self.assertTrue(result.ok)
        self.assertEqual(result.counts["documents"], 1)
        self.assertEqual(result.counts["segments"], 2)
        self.assertEqual(result.counts["drafts"], 1)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM knowledge_page_drafts").fetchone()[0],
            1,
        )

    def test_engine_returns_counts_for_documents_segments_and_drafts(self):
        result = CortexNewEngine(conn=self.conn).ingest_bundle("tenant_engine_test", self.bundle())

        self.assertEqual(result.counts, {
            "objects": 1,
            "documents": 1,
            "segments": 2,
            "relationships": 0,
            "drafts": 1,
        })

    @unittest.mock.patch("app.storage.git_store.init_tenant_repo")
    @unittest.mock.patch("app.storage.git_store.get_tenant_repo_dir")
    @unittest.mock.patch("app.storage.git_store.commit_page_changes")
    @unittest.mock.patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_approve_valid_draft_commits_to_git(self, mock_file_open, mock_commit, mock_get_repo_dir, mock_init_repo):
        mock_get_repo_dir.return_value = "/tmp/repo"
        mock_commit.return_value = "dummy_sha"

        engine = CortexNewEngine(conn=self.conn)
        ingest_res = engine.ingest_bundle("tenant_engine_test", self.bundle())
        self.assertTrue(ingest_res.ok)

        draft_id = ingest_res.stage_results[3].counts.get("drafts") or "draft_4236a282f190"
        # We can fetch the draft ID from database
        draft_row = self.conn.execute("SELECT id FROM knowledge_page_drafts WHERE status = 'DRAFT'").fetchone()
        self.assertIsNotNone(draft_row)
        draft_id = draft_row["id"]

        app_res = engine.approve_draft("tenant_engine_test", draft_id, "test_approver")
        self.assertTrue(app_res.ok)
        self.assertEqual(app_res.commit_sha, "dummy_sha")
        self.assertEqual(app_res.page_id, draft_id.replace("draft_", "page_", 1))

        # Check status updated to APPROVED
        updated = self.conn.execute("SELECT status FROM knowledge_page_drafts WHERE id = ?", (draft_id,)).fetchone()
        self.assertEqual(updated["status"], "APPROVED")

    @unittest.mock.patch("app.storage.git_store.init_tenant_repo")
    def test_approve_invalid_draft_fails_without_commit(self, mock_init_repo):
        engine = CortexNewEngine(conn=self.conn)
        
        # Manually insert an invalid draft in the DB
        self.conn.execute(
            """
            INSERT INTO knowledge_page_drafts (id, tenant_id, title, content, status, validation_passed, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("draft_invalid", "tenant_engine_test", "Bad Draft", "Invalid frontmatter", "DRAFT", 1, "now", "now")
        )
        self.conn.commit()

        app_res = engine.approve_draft("tenant_engine_test", "draft_invalid", "test_approver")
        self.assertFalse(app_res.ok)
        self.assertIn("does not start with YAML frontmatter", app_res.failures[0])
        mock_init_repo.assert_not_called()



if __name__ == "__main__":
    unittest.main()
