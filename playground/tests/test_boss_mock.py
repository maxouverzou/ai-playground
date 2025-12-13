import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Ensure we can import playground.boss
sys.path.append(os.getcwd())
from playground import boss

class MockIssue(dict):
    """A dictionary that allows attribute access to its keys."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self

class TestBoss(unittest.TestCase):
    @patch('playground.boss.GhApi')
    @patch('playground.boss.requests')
    @patch.dict(os.environ, {"GITHUB_PERSONAL_ACCESS_TOKEN": "fake_token", "JULES_API_KEY": "fake_jules_key"})
    def test_boss_creates_comment(self, mock_requests, mock_ghapi_cls):
        # Setup GhApi mock
        mock_ghapi_instance = MagicMock()
        mock_ghapi_cls.return_value = mock_ghapi_instance

        # Setup labels
        label1 = MagicMock()
        label1.name = 'status: ready'
        label2 = MagicMock()
        label2.name = 'priority: high'

        # Setup issue
        issue_data = {
            'number': 123,
            'labels': [label1, label2],
            'title': 'Test Issue',
            'body': 'Test Body'
        }
        issue = MockIssue(issue_data)

        mock_ghapi_instance.issues.list_for_repo.return_value = [issue]

        # Setup requests mock
        mock_response_sessions = MagicMock()
        mock_response_sessions.json.return_value = {"sessions": []}
        mock_response_sessions.raise_for_status.return_value = None

        mock_response_create = MagicMock()
        mock_response_create.json.return_value = {"id": "session_123"}
        mock_response_create.raise_for_status.return_value = None

        def requests_get_side_effect(url, headers, **kwargs):
            if "sessions" in url:
                return mock_response_sessions
            return MagicMock()

        mock_requests.get.side_effect = requests_get_side_effect
        mock_requests.post.return_value = mock_response_create

        # Mock sys.argv
        test_repo = "owner/repo"
        with patch.object(sys, 'argv', ['boss.py', test_repo, '--count', '1']):
            boss.main()

        # Assertions

        # 1. Verify session creation
        mock_requests.post.assert_called_once()
        args, kwargs = mock_requests.post.call_args
        # Verify title is correct
        self.assertEqual(kwargs['json']['title'], "owner/repo#123")

        # 2. Verify comment creation
        expected_url = "https://jules.google.com/session/session_123"

        if mock_ghapi_instance.issues.create_comment.call_count == 0:
            self.fail("issues.create_comment was not called")

        call_args = mock_ghapi_instance.issues.create_comment.call_args
        args, kwargs = call_args

        found_url = False
        # Check positional args
        for arg in args:
            if isinstance(arg, str) and expected_url in arg:
                found_url = True

        # Check kwargs
        if 'body' in kwargs and expected_url in kwargs['body']:
            found_url = True

        self.assertTrue(found_url, f"Comment body did not contain expected URL: {expected_url}. Call args: {call_args}")

if __name__ == '__main__':
    unittest.main()
