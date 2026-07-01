import json
import os
import unittest
import sys
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ingestion.compiler import DraftCompiler
from app.ingestion.engine_models import NormalizedSourceDocument, NormalizedSourceSegment
from app.ingestion.propositions import extract_propositions_from_segments

_LLM_JSON = json.dumps({
    "title": "Doc Title",
    "summary": "Summary of content.",
    "sections": [{"heading": "Intro", "body": "This is introduction.", "evidence_segment_ids": ["srcseg_x"]}],
    "propositions": [
        {"text": "Introduction text.", "evidence_segment_ids": ["srcseg_x"], "source_quotes": ["This is introduction"], "confidence": 0.9, "sensitivity": "team"}
    ],
    "suggested_links": [],
    "knowledge_gaps": [],
})


class TestDraftCompiler(unittest.TestCase):
    def test_compiler_groups_segments_by_heading_path(self):
        segments = [
            NormalizedSourceSegment(document_ref="upload://doc.md", segment_type="paragraph", heading_path=["Intro"], position=1, text="This is introduction."),
            NormalizedSourceSegment(document_ref="upload://doc.md", segment_type="paragraph", heading_path=["Intro"], position=2, text="Intro details."),
            NormalizedSourceSegment(document_ref="upload://doc.md", segment_type="paragraph", heading_path=["Details"], position=3, text="Detailed info."),
        ]
        compiler = DraftCompiler()
        grouped = compiler.group_segments_by_heading(segments)
        self.assertEqual(list(sorted(grouped.keys())), ["Details", "Intro"])
        self.assertEqual(len(grouped["Intro"]), 2)
        self.assertEqual(len(grouped["Details"]), 1)

    @patch("app.ingestion.compiler.get_kimi_client")
    def test_compiler_creates_draft_not_approved_page(self, mock_kimi):
        mock_client = MagicMock()
        mock_client.chat_completion.return_value = _LLM_JSON
        mock_kimi.return_value = mock_client

        doc = NormalizedSourceDocument(source_object_external_id="upload://doc.md", title="Doc Title", body_text="Body content")
        segments = [NormalizedSourceSegment(document_ref="upload://doc.md", segment_type="paragraph", heading_path=["Intro"], position=1, text="This is introduction.")]
        seg_rows = [{"id": "srcseg_x", "content_hash": segments[0].content_hash}]

        compiler = DraftCompiler()
        result = compiler.compile_draft("tenant_test", doc, segments, segment_db_rows=seg_rows)
        self.assertTrue(result["validation_passed"])
        self.assertTrue(result["draft_id"].startswith("draft_"))
        self.assertIn("synthesis_validation", result["content"])
        self.assertIn("Intro", result["content"])

    def test_proposition_requires_evidence_segment_id(self):
        segments = [NormalizedSourceSegment(document_ref="upload://doc.md", segment_type="paragraph", heading_path=["Intro"], position=1, text="This is introduction.")]
        props = extract_propositions_from_segments(segments)
        self.assertTrue(len(props) > 0)
        for p in props:
            self.assertTrue(len(p["evidence_segment_ids"]) > 0)

    @patch("app.ingestion.compiler.get_kimi_client")
    def test_classifier_not_required_for_page_creation(self, mock_kimi):
        """Classifier is not required; LLM compiler handles synthesis."""
        mock_client = MagicMock()
        no_prop_llm = json.dumps({
            "title": "Doc Title", "summary": "Summary.", "sections": [],
            "propositions": [], "suggested_links": [], "knowledge_gaps": [],
        })
        mock_client.chat_completion.return_value = no_prop_llm
        mock_kimi.return_value = mock_client

        doc = NormalizedSourceDocument(source_object_external_id="upload://doc.md", title="Doc Title", body_text="Body content")
        compiler = DraftCompiler()
        result = compiler.compile_draft("tenant_test", doc, [])
        # No propositions → strict_evidence=False → should still pass shape
        self.assertTrue(result["draft_id"].startswith("draft_"))

    @patch("app.ingestion.compiler.get_kimi_client")
    def test_clusterer_not_required_for_page_creation(self, mock_kimi):
        """Clusterer is not required; LLM compiler handles synthesis."""
        mock_client = MagicMock()
        mock_client.chat_completion.return_value = _LLM_JSON
        mock_kimi.return_value = mock_client

        doc = NormalizedSourceDocument(source_object_external_id="upload://doc.md", title="Doc Title", body_text="Body content")
        compiler = DraftCompiler()
        result = compiler.compile_draft("tenant_test", doc, [])
        self.assertTrue(result["draft_id"].startswith("draft_"))


if __name__ == "__main__":
    unittest.main()
