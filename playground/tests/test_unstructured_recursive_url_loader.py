import unittest
from unittest.mock import MagicMock, patch, ANY
import pytest
from langchain_core.documents import Document

# Adjust import based on where UnstructuredRecursiveUrlLoader is located
# Assuming it's in playground/langchain/unstructured_recursive_url_loader.py
from playground.langchain.unstructured_recursive_url_loader import UnstructuredRecursiveUrlLoader

class TestUnstructuredRecursiveUrlLoader(unittest.TestCase):
    def setUp(self):
        self.url = "https://example.com"
        self.loader = UnstructuredRecursiveUrlLoader(url=self.url)

    def test_initialization(self):
        """Test if the loader is initialized with correct default values."""
        loader = UnstructuredRecursiveUrlLoader("https://example.com")
        self.assertEqual(loader.url, "https://example.com")
        self.assertEqual(loader.max_depth, 2)
        self.assertTrue(loader.prevent_outside)
        self.assertEqual(loader.mode, "single")

    @patch("requests.get")
    @patch("unstructured.partition.html.partition_html")
    def test_lazy_load_single_page(self, mock_partition, mock_requests):
        """Test loading a single page without recursion."""
        # Mock Response
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Hello World</p></body></html>"
        mock_response.status_code = 200
        mock_requests.return_value = mock_response

        # Mock Partition
        mock_element = MagicMock()
        mock_element.__str__.return_value = "Hello World"
        mock_partition.return_value = [mock_element]

        loader = UnstructuredRecursiveUrlLoader(url="https://example.com", max_depth=1)
        documents = list(loader.lazy_load())

        self.assertEqual(len(documents), 1)
        self.assertIn("Hello World", documents[0].page_content)
        self.assertEqual(documents[0].metadata["source"], "https://example.com")

    @patch("requests.get")
    @patch("unstructured.partition.html.partition_html")
    def test_recursion(self, mock_partition, mock_requests):
        """Test that the loader follows links recursively."""
        # Setup mocks

        # Responses for different URLs
        def side_effect(url, **kwargs):
            response = MagicMock()
            response.status_code = 200
            if url == "https://example.com":
                response.text = '<html><body><a href="https://example.com/page1">Link</a></body></html>'
            elif url == "https://example.com/page1":
                response.text = '<html><body><p>Page 1 Content</p></body></html>'
            return response

        mock_requests.side_effect = side_effect

        # Partition results
        def partition_side_effect(text, source_url, **kwargs):
            element = MagicMock()
            if source_url == "https://example.com":
                element.__str__.return_value = "Root Page"
            elif source_url == "https://example.com/page1":
                element.__str__.return_value = "Page 1 Content"
            return [element]

        mock_partition.side_effect = partition_side_effect

        loader = UnstructuredRecursiveUrlLoader(url="https://example.com", max_depth=2)
        documents = list(loader.lazy_load())

        # Should load root and page1
        self.assertEqual(len(documents), 2)
        urls = sorted([doc.metadata["source"] for doc in documents])
        self.assertEqual(urls, ["https://example.com", "https://example.com/page1"])

    @patch("requests.get")
    @patch("unstructured.partition.html.partition_html")
    def test_max_depth(self, mock_partition, mock_requests):
        """Test that the loader respects max_depth."""
         # Responses for different URLs
        def side_effect(url, **kwargs):
            response = MagicMock()
            response.status_code = 200
            if url == "https://example.com":
                response.text = '<a href="https://example.com/1">1</a>'
            elif url == "https://example.com/1":
                response.text = '<a href="https://example.com/2">2</a>'
            elif url == "https://example.com/2":
                response.text = '<a href="https://example.com/3">3</a>'
            return response

        mock_requests.side_effect = side_effect
        mock_partition.return_value = [MagicMock(__str__=MagicMock(return_value="content"))]

        # max_depth=2 means: depth 0 (root), depth 1. So it should NOT load depth 2.
        # However, the implementation checks: if depth >= self.max_depth: return.
        # Root is depth 0.
        # It calls _get_child_links_recursive(root, depth=0). Check 0 >= 2 False. Yield root.
        # Find links. Recursively call(link, depth=1). Check 1 >= 2 False. Yield link.
        # Find links. Recursively call(link, depth=2). Check 2 >= 2 True. Return.
        # So it should yield root (depth 0) and depth 1.

        loader = UnstructuredRecursiveUrlLoader(url="https://example.com", max_depth=2)
        documents = list(loader.lazy_load())

        urls = [doc.metadata["source"] for doc in documents]
        self.assertIn("https://example.com", urls)
        self.assertIn("https://example.com/1", urls)
        self.assertNotIn("https://example.com/2", urls)

    @patch("requests.get")
    @patch("unstructured.partition.html.partition_html")
    def test_prevent_outside(self, mock_partition, mock_requests):
        """Test that the loader does not follow outside links."""
        mock_requests.return_value.status_code = 200
        mock_requests.return_value.text = '<a href="https://other.com/page">Outside</a><a href="https://example.com/page">Inside</a>'

        mock_partition.return_value = [MagicMock(__str__=MagicMock(return_value="content"))]

        loader = UnstructuredRecursiveUrlLoader(url="https://example.com", prevent_outside=True)
        # We only mock the root response. If it tries to fetch outside, it will hit the mock too,
        # but we want to check if it tries.
        # Actually, simpler: verify the output documents.

        # If it fetched outside, we'd have more documents or specific calls.
        # But here we mocking requests returns same content for any URL, which would cause infinite loop if not filtered.
        # Wait, if prevent_outside works, it won't even call requests.get for other.com.

        # Let's inspect mock_requests calls.
        loader = UnstructuredRecursiveUrlLoader(url="https://example.com", prevent_outside=True, max_depth=2)
        list(loader.lazy_load())

        # Check arguments called
        called_urls = [call.args[0] for call in mock_requests.call_args_list]
        self.assertIn("https://example.com", called_urls)
        self.assertIn("https://example.com/page", called_urls)
        self.assertNotIn("https://other.com/page", called_urls)

    @patch("requests.get")
    @patch("unstructured.partition.html.partition_html")
    def test_check_response_status(self, mock_partition, mock_requests):
        """Test that the loader handles error status codes."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_requests.return_value = mock_response

        # check_response_status=True, continue_on_failure=True (default)
        # Should log warning and continue (yield nothing for this page)
        loader = UnstructuredRecursiveUrlLoader(url="https://example.com", check_response_status=True)
        documents = list(loader.lazy_load())
        self.assertEqual(len(documents), 0)

        # check_response_status=True, continue_on_failure=False
        # Should raise error
        loader = UnstructuredRecursiveUrlLoader(url="https://example.com", check_response_status=True, continue_on_failure=False)
        with self.assertRaises(ValueError):
            list(loader.lazy_load())

    def test_filter_links(self):
        """Test link filtering."""
        with patch("requests.get") as mock_requests, \
             patch("unstructured.partition.html.partition_html") as mock_partition:

            mock_requests.return_value.status_code = 200
            mock_requests.return_value.text = '<a href="https://example.com/skip">Skip</a><a href="https://example.com/keep">Keep</a>'
            mock_partition.return_value = [MagicMock(__str__=MagicMock(return_value="content"))]

            def link_filter(link):
                return "keep" in link

            loader = UnstructuredRecursiveUrlLoader(
                url="https://example.com",
                link_filter=link_filter,
                max_depth=2
            )

            list(loader.lazy_load())

            called_urls = [call.args[0] for call in mock_requests.call_args_list]
            self.assertIn("https://example.com", called_urls)
            self.assertIn("https://example.com/keep", called_urls)
            self.assertNotIn("https://example.com/skip", called_urls)

if __name__ == "__main__":
    unittest.main()
