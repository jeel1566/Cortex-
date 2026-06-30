import os
import unittest
from unittest.mock import patch
import tempfile
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.retrieval.raw_segment_index import RawSegmentIndex


class TestRawSegmentIndex(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patcher = patch("app.retrieval.raw_segment_index.TENANTS_DIR", self.temp_dir.name)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp_dir.cleanup()

    def dummy_encode_batch(self, texts):
        # Return non-collinear vectors.
        # e.g., first text has [1.0, 0.0, ...], second has [0.0, 1.0, ...]
        embs = []
        for idx, text in enumerate(texts):
            emb = [0.0] * 384
            emb[idx % 384] = 1.0
            embs.append(emb)
        return embs

    def dummy_encode(self, text):
        # Query matches the first vector (seg1)
        emb = [0.0] * 384
        emb[0] = 1.0
        return emb

    @patch("app.retrieval.raw_segment_index.encode_batch")
    @patch("app.retrieval.raw_segment_index.encode")
    def test_raw_segment_index_returns_segment_ids(self, mock_encode, mock_encode_batch):
        mock_encode_batch.side_effect = self.dummy_encode_batch
        mock_encode.side_effect = self.dummy_encode

        idx = RawSegmentIndex(tenant_id="tenant_test")
        segments = [
            {"id": "seg1", "text": "hello world", "content_hash": "hash1"},
            {"id": "seg2", "text": "foo bar", "content_hash": "hash2"},
        ]
        idx.add_segments(segments)
        
        results = idx.search("hello", k=2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][0], "segment:seg1")

    @patch("app.retrieval.raw_segment_index.encode_batch")
    def test_unchanged_segments_are_not_reembedded(self, mock_encode_batch):
        mock_encode_batch.side_effect = self.dummy_encode_batch

        idx = RawSegmentIndex(tenant_id="tenant_test")
        segments = [
            {"id": "seg1", "text": "hello world", "content_hash": "hash1"},
        ]
        idx.add_segments(segments)
        self.assertEqual(mock_encode_batch.call_count, 1)

        idx.add_segments(segments)
        self.assertEqual(mock_encode_batch.call_count, 1)

        segments[0]["content_hash"] = "hash1_updated"
        idx.add_segments(segments)
        self.assertEqual(mock_encode_batch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
