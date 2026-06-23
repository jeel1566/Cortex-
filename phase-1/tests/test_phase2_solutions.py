import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.ingestion.pipeline import load_and_filter_csv
from app.ingestion.synthesizer import synthesize_page, SYNTHESIZER_PROMPT
from app.query_engine import CortexQueryEngine

class TestPhase2Solutions(unittest.TestCase):
    def test_pii_redaction_disabled(self):
        # Verify that load_and_filter_csv does not redact PII like dates or IP addresses
        dummy_csv_content = (
            "ts,subtype,text,channel_id,user,latest_reply\n"
            "1700000000.000000,,Deploy on 2026-06-19 to port 8080 by U123 at test@example.com is completed successfully after testing all features and endpoints.,,U123,\n"
        )
        csv_path = "dummy_messages.csv"
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(dummy_csv_content)
        
        try:
            with patch("app.ingestion.pipeline.load_user_mappings", return_value={"U123": "Alice [U123]"}):
                messages = load_and_filter_csv(csv_path)
                self.assertEqual(len(messages), 1)
                text = messages[0]["text"]
                self.assertIn("2026-06-19", text)
                self.assertIn("8080", text)
                self.assertIn("test@example.com", text)
        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)

    @patch("app.ingestion.synthesizer.get_kimi_client")
    def test_synthesizer_alias_context_and_rules(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat_completion.return_value = "Synthesized content"

        # Verify preservation rules are in prompt
        self.assertIn("CRITICAL PRESERVATION RULES", SYNTHESIZER_PROMPT)

        cluster = [{
            "text": "Hello world",
            "metadata": {"user": "Alice [U123]"}
        }]
        alias_map = {"U123": ["Alice", "Alicia"]}

        synthesize_page(page_index=1, cluster=cluster, alias_map=alias_map)

        mock_client.chat_completion.assert_called_once()
        called_args = mock_client.chat_completion.call_args[0][0]
        user_content = called_args[1]["content"]
        self.assertIn("USER ALIAS INFORMATION", user_content)
        self.assertIn("Alice [U123] is also known as: Alice, Alicia", user_content)

    def test_query_time_alias_expansion(self):
        # Create a mock query engine instance without calling __init__
        engine = object().__new__(CortexQueryEngine)
        engine.alias_map = {"U123": ["Alice", "Alicia"]}

        # Test expansion when alias is mentioned
        expanded = engine._expand_query_with_aliases("Where is Alicia?")
        self.assertIn("Alice", expanded)
        self.assertIn("Note: Alicia is also known as Alice", expanded)

        # Test no expansion if no alias is mentioned
        non_expanded = engine._expand_query_with_aliases("Where is Bob?")
        self.assertEqual(non_expanded, "Where is Bob?")

if __name__ == "__main__":
    unittest.main()
