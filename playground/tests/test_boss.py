import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from playground import boss

class TestBoss(unittest.TestCase):
    @patch('playground.boss.GhApi')
    @patch('playground.boss.requests')
    def test_main_flow(self, mock_requests, mock_ghapi):
        # Setup mocks
        mock_api = MagicMock()
        mock_ghapi.return_value = mock_api

        # Mock labels
        label_mock = MagicMock()
        label_mock.name = "status: ready"

        # Simpler approach: construct a real dict-like object for the issue
        class MockIssue(dict):
             def __getattr__(self, attr):
                 return self[attr]

        issue_data = MockIssue({
            "number": 123,
            "title": "Test Issue",
            "body": "Body of the issue",
            "labels": [label_mock],
        })

        mock_api.issues.list_for_repo.return_value = [issue_data]

        # Mock active sessions (empty)
        mock_response_get = MagicMock()
        mock_response_get.json.return_value = {"sessions": []}
        mock_response_get.status_code = 200

        # Mock create session
        mock_response_post = MagicMock()
        mock_response_post.json.return_value = {"id": "session-123"}
        mock_response_post.status_code = 200

        mock_requests.get.return_value = mock_response_get
        mock_requests.post.return_value = mock_response_post

        # Environment variables
        with patch.dict(os.environ, {"GITHUB_PERSONAL_ACCESS_TOKEN": "token", "JULES_API_KEY": "key"}):
            # Run main with arguments
            with patch('sys.argv', ['boss.py', 'owner/repo', '--count', '1']):
                 boss.main()

        # Verify interactions
        mock_ghapi.assert_called_with(owner='owner', repo='repo', token='token')
        mock_requests.post.assert_called()

        # Verify comment creation
        # Expected URL from create_jules_session (mocked to return specific JSON, but the function formats it)
        # Wait, create_jules_session logic is inside boss.py, so it will format the mocked response.
        # Mocked response: {"id": "session-123"}
        # Expected URL: https://jules.google.com/session/session-123
        expected_url = "https://jules.google.com/session/session-123"
        mock_api.issues.create_comment.assert_called_with(issue_number=123, body=f"Jules session started: {expected_url}")

if __name__ == '__main__':
    unittest.main()
