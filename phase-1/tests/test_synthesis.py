import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.ingestion.pipeline import (
    parse_markdown_with_frontmatter,
    serialize_markdown_with_frontmatter,
    run_ingestion_pipeline
)
from app.ingestion.synthesizer import synthesize_page

class TestSynthesisAndValidation(unittest.TestCase):
    def test_frontmatter_parsing_and_serialization(self):
        markdown_content = """---
id: page_001
title: Remote Work Policy
version: 1
access_level: team
sources:
  - slack://C1/123
---
# Remote Work Policy

We support remote work. [^1]
"""
        metadata, body = parse_markdown_with_frontmatter(markdown_content)
        self.assertEqual(metadata.get("id"), "page_001")
        self.assertEqual(metadata.get("title"), "Remote Work Policy")
        self.assertEqual(metadata.get("access_level"), "team")
        self.assertEqual(metadata.get("sources"), ["slack://C1/123"])
        self.assertEqual(body, "# Remote Work Policy\n\nWe support remote work. [^1]")

        # Update and re-serialize
        metadata["status"] = "APPROVED"
        metadata["synthesis_validation"] = {
            "proposition_coverage": 0.95,
            "hallucination_rate": 0.0,
            "completeness_score": 8,
            "validation_passed": True
        }

        serialized = serialize_markdown_with_frontmatter(metadata, body)
        self.assertTrue(serialized.startswith("---"))
        self.assertIn("status: APPROVED", serialized)
        self.assertIn("proposition_coverage: 0.95", serialized)
        self.assertIn("validation_passed: true", serialized)
        self.assertIn("# Remote Work Policy", serialized)

    @patch('app.ingestion.synthesizer.get_kimi_client')
    def test_synthesize_page_with_feedback(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.chat_completion.return_value = "---yaml---"
        mock_get_client.return_value = mock_client

        cluster = [
            {"text": "Refunding policy", "metadata": {"source_id": "slack://1", "user": "U1"}}
        ]
        
        # Test synthesis WITH feedback
        feedback_msg = "Please cover the refund amount limits."
        synthesize_page(1, cluster, feedback=feedback_msg, temperature=0.2)

        mock_client.chat_completion.assert_called_once()
        args, kwargs = mock_client.chat_completion.call_args
        messages = args[0]
        self.assertEqual(len(messages), 3) # System, User (data), User (feedback)
        self.assertIn("corrections", messages[2]["content"])
        self.assertIn(feedback_msg, messages[2]["content"])
        self.assertEqual(kwargs.get("temperature"), 0.2)

    @patch('app.ingestion.pipeline.validate_page')
    @patch('app.ingestion.pipeline.synthesize_page')
    @patch('app.ingestion.pipeline.cluster_sentences')
    @patch('app.ingestion.pipeline.classify_sentences')
    @patch('app.ingestion.pipeline.load_and_filter_csv')
    def test_pipeline_adaptive_retry_and_frontmatter_write(
        self, mock_load, mock_classify, mock_cluster, mock_synthesize, mock_validate
    ):
        # Setup pipeline mock data
        mock_load.return_value = [
            {"text": "Refunds are 30 days.", "user": "U1", "channel": "C1", "timestamp": "2026-06-16", "source_id": "slack://1"}
        ]
        mock_classify.return_value = ["PRESCRIPTION"]
        mock_cluster.return_value = [
            [{"text": "Refunds are 30 days.", "type": "PRESCRIPTION", "metadata": {"source_id": "slack://1", "user": "U1"}}]
        ]

        # First run: synthesis fails validation (low coverage)
        # Second run: synthesis passes validation
        mock_synthesize.side_effect = [
            "---\ntitle: Draft\n---\n# Draft version",
            "---\ntitle: Final\n---\n# Final version"
        ]
        mock_validate.side_effect = [
            # Attempt 1: Low coverage, completeness
            {
                "proposition_coverage": 0.5,
                "hallucination_rate": 0.0,
                "completeness_score": 5,
                "validation_passed": False,
                "reason": "Failed coverage"
            },
            # Attempt 2: Passed
            {
                "proposition_coverage": 1.0,
                "hallucination_rate": 0.0,
                "completeness_score": 8,
                "validation_passed": True,
                "reason": "Passed validation"
            }
        ]

        pages = run_ingestion_pipeline("dummy.csv", max_messages=1)

        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["status"], "APPROVED")
        self.assertEqual(mock_synthesize.call_count, 2)
        
        # Verify that feedback was formulated and passed to attempt 2
        args1, kwargs1 = mock_synthesize.call_args_list[0]
        args2, kwargs2 = mock_synthesize.call_args_list[1]
        
        self.assertIsNone(kwargs1.get("feedback"))
        self.assertEqual(kwargs1.get("temperature"), 0.3)
        
        self.assertIsNotNone(kwargs2.get("feedback"))
        self.assertIn("coverage was too low", kwargs2.get("feedback"))
        # Verify temperature lowered due to score < 7
        self.assertEqual(kwargs2.get("temperature"), 0.2)

        # Verify validation metadata was serialized into pages[0]["content"] YAML
        content = pages[0]["content"]
        self.assertIn("proposition_coverage: 1.0", content)
        self.assertIn("validation_passed: true", content)
        self.assertIn("status: APPROVED", content)

if __name__ == '__main__':
    unittest.main()
