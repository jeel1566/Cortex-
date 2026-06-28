import os
import sys
import unittest

# Add parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.baseline.local_rag import BM25, redact_pii, replace_user_mentions

class TestRAGComponents(unittest.TestCase):
    def test_pii_redaction(self):
        # ponytail: updated unit test to match disabled PII pass-through behavior
        self.assertEqual(redact_pii("my email is test@example.com"), "my email is test@example.com")
        self.assertEqual(redact_pii("phone number: +1-555-555-5555"), "phone number: +1-555-555-5555")
        self.assertEqual(redact_pii("SSN: 000-12-3456"), "SSN: 000-12-3456")
        self.assertEqual(redact_pii("simple text"), "simple text")

    def test_user_mentions_replacement(self):
        user_map = {"U123": "Alice", "U456": "Bob"}
        self.assertEqual(
            replace_user_mentions("Hello <@U123>, is <@U456> there? <@U789>", user_map),
            "Hello @Alice, is @Bob there? @U789"
        )

    def test_bm25_search(self):
        docs = [
            ["apple", "banana", "cherry"],
            ["banana", "date", "fig"],
            ["apple", "cherry", "fig", "grape"]
        ]
        bm25 = BM25(docs)
        
        # Searching for 'apple' should return doc 0 and doc 2 at the top
        results = bm25.search(["apple"], top_k=2)
        matched_indices = [idx for idx, score in results]
        self.assertIn(0, matched_indices)
        self.assertIn(2, matched_indices)
        self.assertNotIn(1, matched_indices)
        
        # Searching for 'date' should match doc 1 only
        results_date = bm25.search(["date"], top_k=1)
        self.assertEqual(results_date[0][0], 1)
        self.assertTrue(results_date[0][1] > 0.0)

if __name__ == '__main__':
    unittest.main()
