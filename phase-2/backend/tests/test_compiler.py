import os
import unittest
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ingestion.compiler import DraftCompiler
from app.ingestion.engine_models import NormalizedSourceDocument, NormalizedSourceSegment
from app.ingestion.propositions import extract_propositions_from_segments


class TestDraftCompiler(unittest.TestCase):
    def test_compiler_groups_segments_by_heading_path(self):
        doc = NormalizedSourceDocument(
            source_object_external_id="upload://doc.md",
            title="Doc Title",
            body_text="Body content"
        )
        segments = [
            NormalizedSourceSegment(
                document_ref="upload://doc.md",
                segment_type="paragraph",
                heading_path=["Intro"],
                position=1,
                text="This is introduction."
            ),
            NormalizedSourceSegment(
                document_ref="upload://doc.md",
                segment_type="paragraph",
                heading_path=["Intro"],
                position=2,
                text="Intro details."
            ),
            NormalizedSourceSegment(
                document_ref="upload://doc.md",
                segment_type="paragraph",
                heading_path=["Details"],
                position=3,
                text="Detailed info."
            ),
        ]
        compiler = DraftCompiler()
        grouped = compiler.group_segments_by_heading(segments)
        self.assertEqual(list(sorted(grouped.keys())), ["Details", "Intro"])
        self.assertEqual(len(grouped["Intro"]), 2)
        self.assertEqual(len(grouped["Details"]), 1)

    def test_compiler_creates_draft_not_approved_page(self):
        doc = NormalizedSourceDocument(
            source_object_external_id="upload://doc.md",
            title="Doc Title",
            body_text="Body content"
        )
        segments = [
            NormalizedSourceSegment(
                document_ref="upload://doc.md",
                segment_type="paragraph",
                heading_path=["Intro"],
                position=1,
                text="This is introduction."
            )
        ]
        compiler = DraftCompiler()
        result = compiler.compile_draft("tenant_test", doc, segments)
        self.assertTrue(result["validation_passed"])
        self.assertTrue(result["draft_id"].startswith("draft_"))
        self.assertIn("synthesis_validation", result["content"])
        self.assertIn("Intro", result["content"])

    def test_proposition_requires_evidence_segment_id(self):
        segments = [
            NormalizedSourceSegment(
                document_ref="upload://doc.md",
                segment_type="paragraph",
                heading_path=["Intro"],
                position=1,
                text="This is introduction."
            )
        ]
        props = extract_propositions_from_segments(segments)
        self.assertTrue(len(props) > 0)
        for p in props:
            self.assertTrue(len(p["evidence_segment_ids"]) > 0)

    def test_classifier_not_required_for_page_creation(self):
        doc = NormalizedSourceDocument(
            source_object_external_id="upload://doc.md",
            title="Doc Title",
            body_text="Body content"
        )
        compiler = DraftCompiler()
        result = compiler.compile_draft("tenant_test", doc, [])
        self.assertTrue(result["validation_passed"])

    def test_clusterer_not_required_for_page_creation(self):
        doc = NormalizedSourceDocument(
            source_object_external_id="upload://doc.md",
            title="Doc Title",
            body_text="Body content"
        )
        compiler = DraftCompiler()
        result = compiler.compile_draft("tenant_test", doc, [])
        self.assertTrue(result["validation_passed"])


if __name__ == "__main__":
    unittest.main()
