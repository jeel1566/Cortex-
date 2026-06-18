import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add parent directory to sys.path so we can import from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.llm.kimi import CortexLLMClient, KimiClient

class TestLLMProviders(unittest.TestCase):
    @patch('app.llm.kimi.ensure_ollama_running')
    @patch('requests.post')
    def test_ollama_provider(self, mock_post, mock_ensure_ollama):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "mocked ollama response"}}]
        }
        mock_post.return_value = mock_response

        # Test custom parameters for Ollama
        client = CortexLLMClient(
            provider="ollama",
            model="llama3",
            endpoint="http://127.0.0.1:11434/v1"
        )
        
        messages = [{"role": "user", "content": "hello"}]
        res = client.chat_completion(messages)
        
        self.assertEqual(res, "mocked ollama response")
        # Check endpoint parsing and url formatting
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://127.0.0.1:11434/v1/chat/completions")
        self.assertEqual(kwargs['headers']['Authorization'], "Bearer ollama")
        self.assertEqual(kwargs['json']['model'], "llama3")

    @patch('requests.post')
    def test_anthropic_provider(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "mocked anthropic response"}]
        }
        mock_post.return_value = mock_response

        client = CortexLLMClient(
            provider="anthropic",
            model="claude-3-5-sonnet-20240620",
            api_key="sk-ant-test",
            endpoint="https://api.anthropic.com/v1/messages"
        )

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "hello"}
        ]
        res = client.chat_completion(messages)
        
        self.assertEqual(res, "mocked anthropic response")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.anthropic.com/v1/messages")
        self.assertEqual(kwargs['headers']['x-api-key'], "sk-ant-test")
        self.assertEqual(kwargs['headers']['anthropic-version'], "2023-06-01")
        # Check that messages translated to anthropic schema: system extracted, roles mapped
        self.assertEqual(kwargs['json']['system'], "You are a helpful assistant.")
        self.assertEqual(len(kwargs['json']['messages']), 1)
        self.assertEqual(kwargs['json']['messages'][0]['role'], "user")

    @patch('requests.post')
    def test_custom_web_url_provider(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "mocked web_url response"}}]
        }
        mock_post.return_value = mock_response

        client = CortexLLMClient(
            provider="web_url",
            model="custom-model",
            api_key="custom-key",
            endpoint="https://api.openrouter.ai/api/v1"
        )

        messages = [{"role": "user", "content": "hello"}]
        res = client.chat_completion(messages)
        
        self.assertEqual(res, "mocked web_url response")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.openrouter.ai/api/v1/chat/completions")
        self.assertEqual(kwargs['headers']['Authorization'], "Bearer custom-key")

    @patch('requests.post')
    def test_azure_provider(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "mocked azure response"}}]
        }
        mock_post.return_value = mock_response

        client = CortexLLMClient(
            provider="azure",
            model="kimi-k2.5",
            api_key="azure-key",
            endpoint="https://azure-resource.openai.azure.com/openai/deployments/kimi"
        )

        messages = [{"role": "user", "content": "hello"}]
        res = client.chat_completion(messages)
        
        self.assertEqual(res, "mocked azure response")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://azure-resource.openai.azure.com/openai/deployments/kimi/chat/completions")
        self.assertEqual(kwargs['headers']['api-key'], "azure-key")
        self.assertEqual(kwargs['headers']['Authorization'], "Bearer azure-key")

    @patch('requests.post')
    def test_kimi_client_backward_compatibility(self, mock_post):
        # Tests that KimiClient wraps the new client correctly without breaking interface
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "backward compatible response"}}]
        }
        mock_post.return_value = mock_response

        # Temporarily mock LLM_PROVIDER as deepseek
        with patch.dict(os.environ, {"LLM_PROVIDER": "deepseek"}):
            client = KimiClient(
                endpoint="https://api.deepseek.com/v1",
                api_key="deepseek-key",
                model_name="deepseek-chat"
            )
            
            self.assertEqual(client.endpoint, "https://api.deepseek.com/v1")
            self.assertEqual(client.api_key, "deepseek-key")
            self.assertEqual(client.model_name, "deepseek-chat")
            
            res = client.chat_completion([{"role": "user", "content": "hello"}])
            self.assertEqual(res, "backward compatible response")

if __name__ == '__main__':
    unittest.main()
