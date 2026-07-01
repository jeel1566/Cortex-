"""
Tests for LLM compiler, rich propositions, link discovery, and pipeline behavior.
Parts A-H from the Cortex new-engine spec.
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.models import init_database
from app.ingestion.compiler import DraftCompiler, _build_draft_markdown, _rejected_draft_content
from app.ingestion.engine import CortexNewEngine
from app.ingestion.engine_models import (
    NormalizedSourceBundle,
    NormalizedSourceDocument,
    NormalizedSourceObject,
    NormalizedSourceSegment,
)
from app.ingestion.validation import validate_compiled_draft, verify_page_shape


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_doc(ext_id="upload://test.md", title="Test Doc", body="Test body."):
    return NormalizedSourceDocument(
        source_object_external_id=ext_id,
        title=title,
        body_text=body,
    )


def _make_seg(doc_ref="upload://test.md", text="Test sentence.", pos=0, heading=None):
    return NormalizedSourceSegment(
        document_ref=doc_ref,
        segment_type="paragraph",
        heading_path=heading or ["Intro"],
        position=pos,
        text=text,
    )


def _make_bundle(tenant_id="t1", doc_body="Body text for testing."):
    obj = NormalizedSourceObject(
        tenant_id=tenant_id,
        connector_type="upload",
        external_id="upload://test.md",
        object_type="document",
        title="Test Doc",
    )
    doc = _make_doc(body=doc_body)
    seg = _make_seg(text=doc_body)
    return NormalizedSourceBundle(
        tenant_id=tenant_id,
        connector_type="upload",
        objects=[obj],
        documents=[doc],
        segments=[seg],
    )


def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_database(conn)
    conn.execute(
        "INSERT INTO tenants (id, name, created_at, git_repo_path, hnsw_index_path, config) VALUES (?,?,?,?,?,?)",
        ("t1", "T1", "2026-01-01Z", "/tmp/repo", "/tmp/idx", "{}"),
    )
    conn.commit()
    return conn


_VALID_LLM_RESPONSE = json.dumps({
    "title": "Gunicorn Setup Guide",
    "summary": "How to deploy Gunicorn behind Nginx.",
    "sections": [
        {
            "heading": "Introduction",
            "body": "Gunicorn is a WSGI server.",
            "evidence_segment_ids": ["srcseg_abc123"],
        }
    ],
    "propositions": [
        {
            "text": "Gunicorn is a WSGI server used for Python web apps.",
            "evidence_segment_ids": ["srcseg_abc123"],
            "source_quotes": ["Gunicorn is a WSGI server"],
            "confidence": 0.92,
            "sensitivity": "team",
        }
    ],
    "suggested_links": [],
    "knowledge_gaps": [],
})


# ── Part A: LLM synthesis tests ───────────────────────────────────────────────

class TestLLMCompiler(unittest.TestCase):

    @patch("app.ingestion.compiler.get_kimi_client")
    def test_compiler_calls_llm_with_evidence_segments(self, mock_kimi):
        mock_client = MagicMock()
        mock_client.chat_completion.return_value = _VALID_LLM_RESPONSE
        mock_kimi.return_value = mock_client

        doc = _make_doc()
        seg = _make_seg(text="Gunicorn is a WSGI server.")
        seg_rows = [{"id": "srcseg_abc123", "content_hash": seg.content_hash}]

        compiler = DraftCompiler()
        result = compiler.compile_draft("t1", doc, [seg], segment_db_rows=seg_rows)

        self.assertTrue(mock_client.chat_completion.called)
        call_args = mock_client.chat_completion.call_args
        messages = call_args[0][0] if call_args[0] else call_args[1]["messages"]
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        # Prompt must include the real segment ID
        self.assertIn("srcseg_abc123", user_msg)

    @patch("app.ingestion.compiler.get_kimi_client")
    def test_llm_compiler_creates_structured_draft(self, mock_kimi):
        mock_client = MagicMock()
        mock_client.chat_completion.return_value = _VALID_LLM_RESPONSE
        mock_kimi.return_value = mock_client

        doc = _make_doc()
        seg = _make_seg(text="Gunicorn is a WSGI server.")
        seg_rows = [{"id": "srcseg_abc123", "content_hash": seg.content_hash}]

        compiler = DraftCompiler()
        result = compiler.compile_draft("t1", doc, [seg], segment_db_rows=seg_rows)

        self.assertTrue(result["draft_id"].startswith("draft_"))
        self.assertIn("synthesis_validation", result["content"])
        self.assertIn("propositions", result["content"])
        # Rich propositions must be returned
        self.assertTrue(len(result["propositions"]) > 0)
        prop = result["propositions"][0]
        self.assertIn("source_quotes", prop)
        self.assertIn("confidence", prop)
        self.assertIn("evidence_segment_ids", prop)

    @patch("app.ingestion.compiler.get_kimi_client")
    def test_llm_compiler_rejects_prompt_leakage(self, mock_kimi):
        """If LLM returns prompt-leaked content, validator must catch it."""
        mock_client = MagicMock()
        leaked_response = json.dumps({
            "title": "Test",
            "summary": "Based on the provided context...",
            "sections": [{"heading": "H", "body": "Based on the provided data.", "evidence_segment_ids": ["srcseg_abc123"]}],
            "propositions": [
                {"text": "Something", "evidence_segment_ids": ["srcseg_abc123"], "source_quotes": ["x"], "confidence": 0.8, "sensitivity": "team"}
            ],
            "suggested_links": [],
            "knowledge_gaps": [],
        })
        mock_client.chat_completion.return_value = leaked_response
        mock_kimi.return_value = mock_client

        doc = _make_doc()
        seg = _make_seg(text="Some data.")
        seg_rows = [{"id": "srcseg_abc123", "content_hash": seg.content_hash}]

        compiler = DraftCompiler()
        result = compiler.compile_draft("t1", doc, [seg], segment_db_rows=seg_rows)

        # validator should have caught the leakage
        self.assertFalse(result["validation_passed"])
        self.assertTrue(any("prompt leakage" in e for e in result["errors"]))

    @patch("app.ingestion.compiler.get_kimi_client")
    def test_llm_failure_creates_rejected_draft_not_git_page(self, mock_kimi):
        """LLM error must produce a REJECTED draft, never fake content."""
        mock_client = MagicMock()
        mock_client.chat_completion.side_effect = RuntimeError("AI Provider is not configured.")
        mock_kimi.return_value = mock_client

        doc = _make_doc()
        seg = _make_seg()

        compiler = DraftCompiler()
        result = compiler.compile_draft("t1", doc, [seg])

        self.assertFalse(result["validation_passed"])
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["propositions"], [])
        # Content must not contain synthesized knowledge claims
        self.assertIn("Compilation Failed", result["content"])
        self.assertIn("LLM compilation failed", result["errors"][0])

    @patch("app.ingestion.compiler.get_kimi_client")
    def test_llm_not_configured_creates_rejected_draft(self, mock_kimi):
        mock_kimi.side_effect = RuntimeError("AI Provider is not configured.")

        doc = _make_doc()
        compiler = DraftCompiler()
        result = compiler.compile_draft("t1", doc, [])

        self.assertFalse(result["validation_passed"])
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(len(result["propositions"]), 0)


# ── Part B/C: Proposition and markdown tests ─────────────────────────────────

class TestPropositionRichFields(unittest.TestCase):

    def test_proposition_requires_evidence_segment_id(self):
        prop = {"text": "Some claim.", "evidence_segment_ids": []}
        result = validate_compiled_draft("---\nid: \"d\"\ntitle: \"t\"\nsources:\n  - \"s\"\npropositions: []\nsynthesis_validation:\n  proposition_coverage: 0.0\n  hallucination_rate: 0.0\n  completeness_score: 0\n  validation_passed: false\n---\n# T\n", [prop])
        self.assertFalse(result["validation_passed"])
        self.assertTrue(any("evidence_segment_ids" in e for e in result["errors"]))

    def test_proposition_confidence_range_validated(self):
        prop_high = {"text": "Claim.", "evidence_segment_ids": ["srcseg_x"], "confidence": 1.5}
        prop_neg = {"text": "Claim.", "evidence_segment_ids": ["srcseg_x"], "confidence": -0.1}
        content = (
            "---\nid: \"d\"\ntitle: \"t\"\nsources:\n  - \"s\"\n"
            "propositions:\n  - id: \"p1\"\n    text: \"Claim.\"\n"
            "    evidence_segment_ids:\n      - \"srcseg_x\"\n"
            "synthesis_validation:\n  proposition_coverage: 0.0\n"
            "  hallucination_rate: 0.0\n  completeness_score: 0\n  validation_passed: false\n---\n# T\n"
        )
        r1 = validate_compiled_draft(content, [prop_high])
        self.assertTrue(any("outside" in e for e in r1["errors"]))
        r2 = validate_compiled_draft(content, [prop_neg])
        self.assertTrue(any("outside" in e for e in r2["errors"]))

    def test_proposition_invalid_sensitivity_rejected(self):
        prop = {"text": "Claim.", "evidence_segment_ids": ["srcseg_x"], "sensitivity": "secret"}
        content = (
            "---\nid: \"d\"\ntitle: \"t\"\nsources:\n  - \"s\"\n"
            "propositions:\n  - id: \"p1\"\n    text: \"Claim.\"\n"
            "    evidence_segment_ids:\n      - \"srcseg_x\"\n"
            "synthesis_validation:\n  proposition_coverage: 0.0\n"
            "  hallucination_rate: 0.0\n  completeness_score: 0\n  validation_passed: false\n---\n# T\n"
        )
        r = validate_compiled_draft(content, [prop])
        self.assertTrue(any("sensitivity" in e for e in r["errors"]))

    def test_proposition_empty_text_rejected(self):
        prop = {"text": "", "evidence_segment_ids": ["srcseg_x"]}
        content = (
            "---\nid: \"d\"\ntitle: \"t\"\nsources:\n  - \"s\"\n"
            "propositions: []\nsynthesis_validation:\n  proposition_coverage: 0.0\n"
            "  hallucination_rate: 0.0\n  completeness_score: 0\n  validation_passed: false\n---\n# T\n"
        )
        r = validate_compiled_draft(content, [prop])
        self.assertTrue(any("empty text" in e for e in r["errors"]))

    @patch("app.ingestion.compiler.get_kimi_client")
    def test_rich_proposition_saved_with_metadata(self, mock_kimi):
        """Compiler must return propositions with full rich fields (source_quotes, confidence)."""
        mock_client = MagicMock()
        mock_client.chat_completion.return_value = _VALID_LLM_RESPONSE
        mock_kimi.return_value = mock_client

        doc = _make_doc()
        seg = _make_seg(text="Gunicorn is a WSGI server.")
        seg_rows = [{"id": "srcseg_abc123", "content_hash": seg.content_hash}]

        compiler = DraftCompiler()
        result = compiler.compile_draft("t1", doc, [seg], segment_db_rows=seg_rows)

        self.assertTrue(result["validation_passed"], f"Errors: {result['errors']}")
        props = result["propositions"]
        self.assertTrue(len(props) > 0)
        for p in props:
            self.assertIn("source_quotes", p)
            self.assertIn("confidence", p)
            self.assertIn("evidence_segment_ids", p)
            self.assertIsInstance(p["confidence"], float)
            self.assertTrue(0.0 <= p["confidence"] <= 1.0)


# ── Part D: Link discovery tests ──────────────────────────────────────────────

class TestLinkDiscovery(unittest.TestCase):

    def _write_page(self, repo_dir, page_id, title, prop_text):
        content = (
            "---\n"
            f'id: "{page_id}"\n'
            f'title: "{title}"\n'
            "sources:\n  - \"src\"\n"
            "propositions:\n"
            f'  - id: "p1"\n    text: "{prop_text}"\n    evidence_segment_ids:\n      - "seg_1"\n'
            "synthesis_validation:\n  proposition_coverage: 1.0\n  hallucination_rate: 0.0\n"
            "  completeness_score: 9\n  validation_passed: true\n"
            "---\n"
            f"# {title}\n\n{prop_text}\n"
        )
        os.makedirs(repo_dir, exist_ok=True)
        with open(os.path.join(repo_dir, f"{page_id}.md"), "w") as f:
            f.write(content)

    def test_link_discovery_suggests_related_existing_page(self):
        from app.ingestion.link_discovery import discover_links
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_page(tmpdir, "page_gunicorn", "Gunicorn Setup", "Gunicorn is a WSGI server.")
            links = discover_links(
                "t1",
                "Gunicorn Deployment Guide",
                [{"text": "Gunicorn serves Python applications."}],
                tmpdir,
            )
            # Should find at least one link to the existing gunicorn page
            self.assertTrue(len(links) > 0)
            self.assertEqual(links[0]["target_page_id"], "page_gunicorn")

    def test_unknown_link_target_rejected(self):
        """validate_compiled_draft must reject links to non-existent pages."""
        content = (
            "---\nid: \"d\"\ntitle: \"t\"\nsources:\n  - \"s\"\n"
            "propositions:\n  - id: \"p1\"\n    text: \"Claim.\"\n"
            "    evidence_segment_ids:\n      - \"srcseg_x\"\n"
            "primary_links:\n  - \"page_does_not_exist\"\n"
            "synthesis_validation:\n  proposition_coverage: 0.0\n"
            "  hallucination_rate: 0.0\n  completeness_score: 0\n  validation_passed: false\n---\n# T\n"
        )
        r = validate_compiled_draft(content, [], approved_page_ids=["page_real"])
        self.assertFalse(r["validation_passed"])
        self.assertTrue(any("does not exist" in e for e in r["errors"]))

    def test_conflict_link_requires_evidence(self):
        from app.ingestion.link_discovery import discover_links
        # conflict links returned by LLM without evidence_segment_ids still pass through,
        # but validator should warn if conflict link has no evidence in propositions.
        # This test checks that the link dict always has the key.
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_page(tmpdir, "page_a", "Topic A", "A is true.")
            with patch("app.ingestion.link_discovery.get_kimi_client") as mock_kimi:
                mock_client = MagicMock()
                mock_client.chat_completion.return_value = json.dumps([
                    {
                        "target_page_id": "page_a",
                        "relationship_type": "conflict",
                        "reason": "Contradicts A.",
                        "evidence_segment_ids": ["srcseg_x"],
                    }
                ])
                mock_kimi.return_value = mock_client
                links = discover_links("t1", "Topic A Rebuttal", [{"text": "A is false."}], tmpdir)
            self.assertTrue(any(l["relationship_type"] == "conflict" for l in links))
            conflict = next(l for l in links if l["relationship_type"] == "conflict")
            self.assertIn("evidence_segment_ids", conflict)

    def test_no_pages_returns_empty_links(self):
        from app.ingestion.link_discovery import discover_links
        with tempfile.TemporaryDirectory() as tmpdir:
            links = discover_links("t1", "New Topic", [], tmpdir)
            self.assertEqual(links, [])


# ── Part E: Validation tests ──────────────────────────────────────────────────

class TestValidation(unittest.TestCase):

    def _valid_content(self, seg_id="srcseg_x"):
        return (
            "---\n"
            'id: "draft_001"\n'
            'title: "Test Page"\n'
            "sources:\n  - \"src\"\n"
            "propositions:\n"
            f'  - id: "prop_1"\n    text: "Claim."\n    evidence_segment_ids:\n      - "{seg_id}"\n'
            "synthesis_validation:\n  proposition_coverage: 0.9\n  hallucination_rate: 0.0\n"
            "  completeness_score: 8\n  validation_passed: false\n"
            "---\n# Test Page\n\nBody text.\n"
        )

    def test_valid_draft_passes(self):
        r = validate_compiled_draft(self._valid_content(), [{"text": "Claim.", "evidence_segment_ids": ["srcseg_x"]}])
        self.assertTrue(r["validation_passed"])
        self.assertIn("validated_at", r)

    def test_assistant_commentary_caught(self):
        content = self._valid_content() + "\nassistant response: here is the answer."
        with self.assertRaises(ValueError) as ctx:
            verify_page_shape(content)
        self.assertIn("prompt leakage", str(ctx.exception))

    def test_allowed_segment_ids_enforced(self):
        r = validate_compiled_draft(
            self._valid_content("srcseg_x"),
            [{"text": "Claim.", "evidence_segment_ids": ["srcseg_x"]}],
            allowed_segment_ids=["srcseg_other"],
        )
        self.assertFalse(r["validation_passed"])
        self.assertTrue(any("does not exist" in e for e in r["errors"]))


# ── Part F: LLM failure / pipeline isolation tests ───────────────────────────

class TestLLMFailureBehavior(unittest.TestCase):

    @patch("app.ingestion.compiler.get_kimi_client")
    def test_raw_segments_searchable_before_llm_compile_finishes(self, mock_kimi):
        """Source storage must succeed even if LLM errors."""
        mock_kimi.side_effect = RuntimeError("LLM not configured")
        conn = _make_conn()
        bundle = _make_bundle()
        engine = CortexNewEngine(conn=conn)

        with patch("app.storage.git_store.init_tenant_repo"), \
             patch("app.storage.git_store.get_tenant_repo_dir", return_value="/tmp"), \
             patch("app.storage.git_store.commit_page_changes", return_value="sha"), \
             patch("app.retrieval.raw_segment_index.encode_batch", return_value=[[0.0] * 384]), \
             patch("app.retrieval.raw_segment_index.encode", return_value=[0.0] * 384):
            result = engine.ingest_bundle("t1", bundle)

        # Source segments are stored regardless
        segs = conn.execute("SELECT id FROM source_segments WHERE tenant_id = 't1'").fetchall()
        self.assertTrue(len(segs) > 0, "Segments must be stored even when LLM fails")

        # Draft must be REJECTED, not missing
        draft = conn.execute("SELECT status FROM knowledge_page_drafts WHERE tenant_id = 't1'").fetchone()
        self.assertIsNotNone(draft)
        self.assertEqual(draft["status"], "REJECTED")

    @patch("app.ingestion.compiler.get_kimi_client")
    def test_rejected_draft_is_not_committed_to_git(self, mock_kimi):
        """A REJECTED draft must not be committable via approve_draft."""
        mock_kimi.side_effect = RuntimeError("LLM not configured")
        conn = _make_conn()
        bundle = _make_bundle()
        engine = CortexNewEngine(conn=conn)

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.storage.git_store.init_tenant_repo"), \
                 patch("app.storage.git_store.get_tenant_repo_dir", return_value=tmpdir), \
                 patch("app.storage.git_store.commit_page_changes", return_value="sha"), \
                 patch("app.retrieval.raw_segment_index.encode_batch", return_value=[[0.0] * 384]), \
                 patch("app.retrieval.raw_segment_index.encode", return_value=[0.0] * 384):
                engine.ingest_bundle("t1", bundle)

        draft = conn.execute("SELECT id FROM knowledge_page_drafts WHERE tenant_id = 't1' AND status = 'REJECTED'").fetchone()
        self.assertIsNotNone(draft)
        draft_id = draft["id"]

        # Attempting to approve a rejected draft must fail — shape check catches it
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch("app.storage.git_store.init_tenant_repo"), \
             patch("app.storage.git_store.get_tenant_repo_dir", return_value=tmpdir), \
             patch("app.storage.git_store.commit_page_changes", return_value="sha"), \
             patch("app.llm.embedding.encode", return_value=[0.0] * 384):
            app_res = engine.approve_draft("t1", draft_id, "admin")

        self.assertFalse(app_res.ok)

    def test_draft_created_before_approval_but_not_committed(self):
        """Draft exists in DB but not in Git until approved."""
        conn = _make_conn()
        bundle = _make_bundle()

        # Build LLM response using the actual segment content hash for ID alignment
        seg = bundle.segments[0]
        llm_json = json.dumps({
            "title": "Test Doc", "summary": "Body text for testing.",
            "sections": [{"heading": "General", "body": "Body text for testing.", "evidence_segment_ids": [f"srcseg_{seg.content_hash[:12]}"]}],
            "propositions": [{"text": "Body text.", "evidence_segment_ids": [f"srcseg_{seg.content_hash[:12]}"], "source_quotes": ["Body text"], "confidence": 0.9, "sensitivity": "team"}],
            "suggested_links": [], "knowledge_gaps": [],
        })

        with patch("app.ingestion.compiler.get_kimi_client") as mock_kimi, \
             patch("app.storage.git_store.commit_page_changes") as mock_commit:
            mock_client = MagicMock()
            mock_client.chat_completion.return_value = llm_json
            mock_kimi.return_value = mock_client

            engine = CortexNewEngine(conn=conn)
            engine.ingest_bundle("t1", bundle)
            # commit must not have been called during ingest
            mock_commit.assert_not_called()

        draft = conn.execute("SELECT status FROM knowledge_page_drafts WHERE tenant_id = 't1'").fetchone()
        self.assertEqual(draft["status"], "DRAFT")


# ── Part H: End-to-end pipeline test ─────────────────────────────────────────

class TestEndToEndPipeline(unittest.TestCase):

    @patch("app.retrieval.raw_segment_index.encode_batch")
    @patch("app.retrieval.raw_segment_index.encode")
    @patch("app.llm.embedding.encode")
    @patch("app.retrieval.hybrid_query.get_kimi_client")
    @patch("app.storage.git_store.init_tenant_repo")
    @patch("app.storage.git_store.get_tenant_repo_dir")
    @patch("app.storage.git_store.commit_page_changes")
    @patch("app.ingestion.compiler.get_kimi_client")
    def test_full_pipeline_upload_to_query(
        self, mock_compiler_kimi, mock_commit, mock_repo_dir, mock_init_repo,
        mock_query_kimi, mock_embed, mock_idx_encode, mock_idx_batch,
    ):
        mock_idx_batch.side_effect = lambda texts: [[0.1] * 384 for _ in texts]
        mock_idx_encode.return_value = [0.1] * 384
        mock_embed.return_value = [0.1] * 384

        # Mock compiler LLM
        mock_compiler_client = MagicMock()
        mock_compiler_client.chat_completion.return_value = _VALID_LLM_RESPONSE
        mock_compiler_kimi.return_value = mock_compiler_client

        # Mock query LLM
        mock_query_client = MagicMock()
        mock_query_client.chat_completion.return_value = "Gunicorn is a WSGI server for Python."
        mock_query_kimi.return_value = mock_query_client

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = os.path.join(tmpdir, "t1", "repo")
            os.makedirs(repo_dir, exist_ok=True)
            mock_repo_dir.return_value = repo_dir
            mock_commit.return_value = "commit_abc"

            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            init_database(conn)
            conn.execute(
                "INSERT INTO tenants (id, name, created_at, git_repo_path, hnsw_index_path, config) VALUES (?,?,?,?,?,?)",
                ("t1", "T1", "2026-01-01Z", repo_dir, "/tmp/idx", "{}"),
            )
            conn.commit()

            # 1. Build and ingest bundle
            from app.ingestion.connectors.local_upload import LocalUploadAdapter
            fpath = os.path.join(tmpdir, "guide.md")
            with open(fpath, "w") as f:
                f.write("# Gunicorn Setup\n\nDeploy Gunicorn behind Nginx.\n")

            adapter = LocalUploadAdapter(tenant_id="t1", file_path=fpath)
            bundle = adapter.normalize()

            engine = CortexNewEngine(conn=conn)

            with patch("app.config.TENANTS_DIR", tmpdir):
                ingest_res = engine.ingest_bundle("t1", bundle)

            self.assertTrue(ingest_res.ok)
            self.assertGreater(ingest_res.counts["segments"], 0, "Raw segments must be stored")
            self.assertGreater(ingest_res.counts["drafts"], 0, "Draft must be created")

            # 2. Raw segments searchable before approval
            segs = conn.execute("SELECT id FROM source_segments WHERE tenant_id = 't1'").fetchall()
            self.assertTrue(len(segs) > 0)

            # 3. Draft exists but not in Git
            draft_row = conn.execute("SELECT * FROM knowledge_page_drafts WHERE status = 'DRAFT'").fetchone()
            self.assertIsNotNone(draft_row)
            draft_id = draft_row["id"]

            # 4. Approve -> Git commit
            with patch("app.config.TENANTS_DIR", tmpdir):
                app_res = engine.approve_draft("t1", draft_id, "admin")

            self.assertTrue(app_res.ok, f"Approval failed: {app_res.failures}")
            self.assertEqual(app_res.commit_sha, "commit_abc")
            mock_commit.assert_called_once()

            # 5. Query returns cited answer from approved page
            from app.retrieval.hybrid_query import HybridQueryEngine
            with patch("app.config.TENANTS_DIR", tmpdir):
                qe = HybridQueryEngine(tenant_id="t1", conn=conn)
                result = qe.query("How to deploy Gunicorn?", user={"clearance_level": "team", "department": None, "role": "member"})

            self.assertIn("answer", result)
            self.assertIn("citations", result)
            self.assertIn("pages_read", result)
            self.assertIn("source_segments_read", result)
            self.assertIn("confidence", result)
            self.assertIn("latency_ms", result)


if __name__ == "__main__":
    unittest.main()
