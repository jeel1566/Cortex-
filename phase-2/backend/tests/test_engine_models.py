import os
import unittest

from pydantic import ValidationError

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ingestion.engine_models import (
    EngineIngestResult,
    EngineStageResult,
    NormalizedSourceBundle,
    NormalizedSourceDocument,
    NormalizedSourceObject,
    NormalizedSourceSegment,
)


class TestEngineModels(unittest.TestCase):
    def test_normalized_bundle_rejects_empty_documents(self):
        with self.assertRaises(ValidationError):
            NormalizedSourceBundle(
                tenant_id="tenant_engine_test",
                connector_type="local_upload",
                objects=[],
                documents=[],
            )

    def test_source_segment_requires_text_and_position(self):
        with self.assertRaises(ValidationError):
            NormalizedSourceSegment(document_ref="doc", position=-1, text="Nope")
        with self.assertRaises(ValidationError):
            NormalizedSourceSegment(document_ref="doc", position=0, text="   ")

    def test_engine_result_reports_stage_counts(self):
        result = EngineIngestResult(
            tenant_id="tenant_engine_test",
            ok=True,
            counts={"documents": 1},
            stage_results=[EngineStageResult(stage="store", ok=True, counts={"documents": 1})],
        )
        self.assertEqual(result.counts["documents"], 1)
        self.assertEqual(result.stage_results[0].counts["documents"], 1)

    def test_valid_bundle_fills_content_hashes(self):
        bundle = NormalizedSourceBundle(
            tenant_id="tenant_engine_test",
            connector_type="local_upload",
            objects=[
                NormalizedSourceObject(
                    tenant_id="tenant_engine_test",
                    connector_type="local_upload",
                    external_id="upload://a.md",
                    object_type="file",
                    title="A",
                )
            ],
            documents=[
                NormalizedSourceDocument(
                    source_object_external_id="upload://a.md",
                    title="A",
                    body_text="hello",
                )
            ],
        )
        self.assertTrue(bundle.objects[0].content_hash)
        self.assertTrue(bundle.documents[0].content_hash)


if __name__ == "__main__":
    unittest.main()
