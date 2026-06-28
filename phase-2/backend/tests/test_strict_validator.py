import os
import sys
import unittest
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.ingestion.validation import verify_page_shape

class TestStrictValidator(unittest.TestCase):
    def test_valid_page_shape_passes(self):
        valid_content = (
            "---\n"
            "id: \"page_001\"\n"
            "title: \"WSGI Server Setup\"\n"
            "sources:\n"
            "  - \"notion://page/123\"\n"
            "propositions:\n"
            "  - \"Gunicorn runs as a WSGI server.\"\n"
            "synthesis_validation:\n"
            "  proposition_coverage: 1.0\n"
            "  hallucination_rate: 0.0\n"
            "  completeness_score: 9\n"
            "---\n"
            "## Content section\n"
            "Gunicorn is the recommended WSGI server."
        )
        self.assertTrue(verify_page_shape(valid_content))

    def test_missing_frontmatter_separator_fails(self):
        content = "title: WSGI Server\nno frontmatter separators."
        with self.assertRaises(ValueError) as context:
            verify_page_shape(content)
        self.assertIn("does not start with YAML frontmatter separator", str(context.exception))

    def test_missing_closing_separator_fails(self):
        content = "---\ntitle: WSGI Server\nid: page_001"
        with self.assertRaises(ValueError) as context:
            verify_page_shape(content)
        self.assertIn("lacks a closing YAML frontmatter separator", str(context.exception))

    def test_missing_mandatory_keys_fails(self):
        content = (
            "---\n"
            "id: \"page_001\"\n"
            "title: \"WSGI Server\"\n"
            "---\n"
        )
        with self.assertRaises(ValueError) as context:
            verify_page_shape(content)
        self.assertIn("missing required key", str(context.exception))

    def test_prompt_leakage_blacklist_fails(self):
        content = (
            "---\n"
            "id: \"page_001\"\n"
            "title: \"WSGI Server\"\n"
            "sources:\n"
            "  - \"notion://page/123\"\n"
            "propositions:\n"
            "  - \"Gunicorn runs as WSGI.\"\n"
            "synthesis_validation:\n"
            "  proposition_coverage: 1.0\n"
            "  hallucination_rate: 0.0\n"
            "  completeness_score: 9\n"
            "---\n"
            "Expected Output: This contains leaked meta-data."
        )
        with self.assertRaises(ValueError) as context:
            verify_page_shape(content)
        self.assertIn("contains prompt leakage", str(context.exception))

        content_closing = content.replace("Expected Output:", "</output_format>")
        with self.assertRaises(ValueError) as context:
            verify_page_shape(content_closing)
        self.assertIn("contains prompt leakage", str(context.exception))
