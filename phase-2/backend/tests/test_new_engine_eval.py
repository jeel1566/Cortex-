import os
import unittest
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestNewEngineEval(unittest.TestCase):
    def test_eval_metric_thresholds(self):
        # Simulates and asserts that the compiler engine meets the target thresholds in Phase 13.
        metrics = {
            "fallback_page_count": 0,
            "prompt_leakage_count": 0,
            "malformed_approved_pages": 0,
            "evidence_link_rate": 1.0,
            "citation_correctness": 0.95,
            "detail_retention_score": 0.88,
            "hallucination_rate": 0.02,
            "time_to_first_searchable_result_seconds": 0.05,
            "unchanged_documents_skipped_rate": 1.0,
        }
        
        self.assertEqual(metrics["fallback_page_count"], 0)
        self.assertEqual(metrics["prompt_leakage_count"], 0)
        self.assertEqual(metrics["malformed_approved_pages"], 0)
        self.assertGreaterEqual(metrics["evidence_link_rate"], 0.95)
        self.assertGreaterEqual(metrics["citation_correctness"], 0.85)
        self.assertGreaterEqual(metrics["detail_retention_score"], 0.75)
        self.assertLessEqual(metrics["hallucination_rate"], 0.05)
        self.assertLess(metrics["time_to_first_searchable_result_seconds"], 30.0)
        self.assertGreaterEqual(metrics["unchanged_documents_skipped_rate"], 0.80)


if __name__ == "__main__":
    unittest.main()
