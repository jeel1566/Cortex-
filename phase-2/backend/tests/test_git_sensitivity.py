import os
import shutil
import unittest
from unittest.mock import MagicMock, patch

# Adjust sys.path to backend directory
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.storage.git_store import init_tenant_repo, commit_page_changes, get_tenant_repo_dir
from app.ingestion.pipeline import run_ingestion_pipeline

class TestGitSensitivity(unittest.TestCase):
    def setUp(self):
        self.tenant_id = "test_tenant_git_sens"
        self.repo_dir = get_tenant_repo_dir(self.tenant_id)
        self.cleanup()

    def tearDown(self):
        self.cleanup()

    def cleanup(self):
        import gc
        gc.collect()
        
        def onerror(func, path, exc_info):
            import stat
            os.chmod(path, stat.S_IWRITE)
            func(path)
            
        tenant_path = os.path.dirname(self.repo_dir)
        if os.path.exists(tenant_path):
            try:
                shutil.rmtree(tenant_path, onerror=onerror)
            except Exception:
                pass

    def test_git_repo_init(self):
        repo = init_tenant_repo(self.tenant_id)
        self.assertTrue(os.path.exists(os.path.join(self.repo_dir, ".git")))
        self.assertTrue(os.path.exists(os.path.join(self.repo_dir, "README.md")))
        
        # Check that there is an initial commit
        commits = list(repo.iter_commits())
        self.assertEqual(len(commits), 1)
        self.assertIn("Setup tenant knowledge base", commits[0].message)
        repo.close()

    @patch('app.ingestion.pipeline.classify_sentences')
    @patch('app.ingestion.pipeline.synthesize_page')
    @patch('app.ingestion.pipeline.validate_page')
    @patch('app.ingestion.pipeline.encode')
    def test_ingestion_git_commit_and_sensitivity(self, mock_encode, mock_validate, mock_synthesize, mock_classify):
        # Setup mocks
        mock_classify.return_value = ["PRESCRIPTION", "OUTCOME"]
        mock_encode.return_value = [0.1] * 384
        mock_validate.return_value = {
            "proposition_coverage": 0.95,
            "hallucination_rate": 0.00,
            "completeness_score": 8,
            "validation_passed": True,
            "reason": "Perfect page summary"
        }
        
        # Mock LLM generated page with YAML propositions containing sensitivity tags
        mock_synthesize.return_value = """---
id: page_001
title: Test Page
version: 1
last_updated: 2026-06-17T10:00:00Z
access_level: team
primary_links: []
secondary_links: []
sources:
  - slack://test_channel/123.456
propositions:
  - id: prop_1
    text: "The server requires a public key to login."
    sensitivity: public
  - id: prop_2
    text: "The root password is supersecret."
    sensitivity: confidential
---
# Test Page
Claims are citation-marked [^1].
"""
        # Run pipeline
        messages = [
            {"text": "Sentence 1. Sentence 2.", "user": "U1", "channel": "C1", "timestamp": "123.456"}
        ]
        
        pages = run_ingestion_pipeline(self.tenant_id, messages)
        
        # Verify page created and contains sensitivity tags
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["page_id"], "page_001")
        self.assertIn("sensitivity: public", pages[0]["content"])
        self.assertIn("sensitivity: confidential", pages[0]["content"])
        
        # Verify file committed in Git
        repo = init_tenant_repo(self.tenant_id)
        commits = list(repo.iter_commits())
        # We expect 2 commits: Initial commit + Ingestion page commit
        self.assertEqual(len(commits), 2)
        self.assertIn("Create page_001", commits[0].message)
        repo.close()

if __name__ == '__main__':
    unittest.main()
