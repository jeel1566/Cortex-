import os
import tempfile
import unittest
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ingestion.connectors.local_upload import LocalUploadAdapter


class TestLocalUploadAdapter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_temp_file(self, filename: str, content: bytes) -> str:
        path = os.path.join(self.temp_dir.name, filename)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def test_local_upload_markdown_preserves_headings(self):
        content = b"# Main Title\nThis is paragraph 1.\n## Sub Section\nThis is sub paragraph."
        path = self.write_temp_file("test.md", content)
        
        adapter = LocalUploadAdapter(tenant_id="tenant_test", file_path=path)
        bundle = adapter.normalize()
        
        self.assertEqual(len(bundle.documents), 1)
        self.assertEqual(bundle.documents[0].title, "test")
        
        self.assertEqual(len(bundle.segments), 4)
        
        self.assertEqual(bundle.segments[0].segment_type, "heading")
        self.assertEqual(bundle.segments[0].text, "Main Title")
        self.assertEqual(bundle.segments[0].heading_path, ["Main Title"])
        
        self.assertEqual(bundle.segments[1].segment_type, "paragraph")
        self.assertEqual(bundle.segments[1].text, "This is paragraph 1.")
        self.assertEqual(bundle.segments[1].heading_path, ["Main Title"])
        
        self.assertEqual(bundle.segments[2].segment_type, "heading")
        self.assertEqual(bundle.segments[2].text, "Sub Section")
        self.assertEqual(bundle.segments[2].heading_path, ["Main Title", "Sub Section"])
        
        self.assertEqual(bundle.segments[3].segment_type, "paragraph")
        self.assertEqual(bundle.segments[3].text, "This is sub paragraph.")
        self.assertEqual(bundle.segments[3].heading_path, ["Main Title", "Sub Section"])

    def test_local_upload_txt_creates_document_and_segments(self):
        content = b"Paragraph one.\n\nParagraph two."
        path = self.write_temp_file("test.txt", content)
        
        adapter = LocalUploadAdapter(tenant_id="tenant_test", file_path=path)
        bundle = adapter.normalize()
        
        self.assertEqual(len(bundle.documents), 1)
        self.assertEqual(len(bundle.segments), 2)
        self.assertEqual(bundle.segments[0].text, "Paragraph one.")
        self.assertEqual(bundle.segments[1].text, "Paragraph two.")

    def test_local_upload_csv_creates_tabular_segments(self):
        content = b"name,age,city\nAyush,22,Mumbai\nJeel,23,Surat"
        path = self.write_temp_file("test.csv", content)
        
        adapter = LocalUploadAdapter(tenant_id="tenant_test", file_path=path)
        bundle = adapter.normalize()
        
        self.assertEqual(len(bundle.documents), 1)
        self.assertEqual(len(bundle.segments), 3)
        self.assertEqual(bundle.segments[0].segment_type, "table_row")
        self.assertEqual(bundle.segments[0].text, "name, age, city")
        self.assertEqual(bundle.segments[1].text, "Ayush, 22, Mumbai")
        self.assertEqual(bundle.segments[2].text, "Jeel, 23, Surat")

    def test_unsupported_binary_file_returns_clear_error(self):
        path = self.write_temp_file("test.xyz", b"some content")
        adapter = LocalUploadAdapter(tenant_id="tenant_test", file_path=path)
        with self.assertRaises(ValueError) as ctx:
            adapter.normalize()
        self.assertIn("Unsupported file format", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
