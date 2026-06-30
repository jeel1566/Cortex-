import os
import sqlite3
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.models import init_database
from app.ingestion.source_store import (
    create_source_document,
    create_source_object,
    create_source_relationship,
    create_source_segments,
    find_source_object_by_hash,
    list_source_segments,
)


class TestSourceStore(unittest.TestCase):
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
            ("tenant_source_test", "Tenant Source Test", "2026-06-30T00:00:00Z", "/tmp/repo", "/tmp/index", "{}"),
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_stores_normalized_source_document_segments_and_relationship(self):
        source_object = create_source_object(
            self.conn,
            tenant_id="tenant_source_test",
            connector_type="local_upload",
            external_id="upload://sales-playbook.md",
            object_type="file",
            title="Sales Playbook",
            url="file://sales-playbook.md",
            author="Ayush",
            raw_json={"filename": "sales-playbook.md"},
            content="## Pricing\nEnterprise customers use annual billing.",
        )
        document = create_source_document(
            self.conn,
            tenant_id="tenant_source_test",
            source_object_id=source_object["id"],
            title="Sales Playbook",
            body_text="## Pricing\nEnterprise customers use annual billing.",
            metadata={"parser": "markdown"},
        )
        segments = create_source_segments(
            self.conn,
            tenant_id="tenant_source_test",
            document_id=document["id"],
            segments=[
                {
                    "segment_type": "heading",
                    "heading_path": "Pricing",
                    "position": 1,
                    "text": "Pricing",
                    "metadata": {"level": 2},
                },
                {
                    "segment_type": "paragraph",
                    "heading_path": "Pricing",
                    "position": 2,
                    "text": "Enterprise customers use annual billing.",
                    "metadata": {},
                },
            ],
        )
        relationship = create_source_relationship(
            self.conn,
            tenant_id="tenant_source_test",
            from_object_id=source_object["id"],
            to_object_id=source_object["id"],
            relationship_type="self",
            metadata={"reason": "smoke"},
        )

        self.assertEqual(source_object["connector_type"], "local_upload")
        self.assertEqual(document["source_object_id"], source_object["id"])
        self.assertEqual([s["segment_type"] for s in segments], ["heading", "paragraph"])
        self.assertEqual(relationship["relationship_type"], "self")
        self.assertEqual(
            [s["text"] for s in list_source_segments(self.conn, document["id"])],
            ["Pricing", "Enterprise customers use annual billing."],
        )

    def test_source_object_content_hash_dedupes_unchanged_content(self):
        first = create_source_object(
            self.conn,
            tenant_id="tenant_source_test",
            connector_type="notion",
            external_id="notion://page/abc",
            object_type="page",
            title="Roadmap",
            url="https://notion.so/abc",
            author="notion",
            raw_json={},
            content="same content",
        )
        second = create_source_object(
            self.conn,
            tenant_id="tenant_source_test",
            connector_type="notion",
            external_id="notion://page/abc",
            object_type="page",
            title="Roadmap updated title",
            url="https://notion.so/abc",
            author="notion",
            raw_json={},
            content="same content",
        )

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["title"], "Roadmap updated title")
        self.assertEqual(find_source_object_by_hash(self.conn, "tenant_source_test", second["content_hash"])["id"], first["id"])


if __name__ == "__main__":
    unittest.main()
