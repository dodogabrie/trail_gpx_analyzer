import unittest
import os
from unittest.mock import Mock, patch, MagicMock
from src.strava.api import download_streams, fetch_activities, get_rate_limit_status
import pandas as pd


class TestStravaAPI(unittest.TestCase):
    """Test Strava API functions with mocked responses."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_token = "test_access_token"
        self.test_activity_id = 12345678
        self.test_output_dir = "tests/test_data"

        # Create test output directory
        os.makedirs(self.test_output_dir, exist_ok=True)

    def tearDown(self):
        """Clean up test files."""
        # Remove test CSV files
        if os.path.exists(self.test_output_dir):
            for file in os.listdir(self.test_output_dir):
                if file.endswith('.csv'):
                    os.remove(os.path.join(self.test_output_dir, file))
            os.rmdir(self.test_output_dir)

    @patch('src.strava.api.r.get')
    @patch('src.strava.api._rate_limiter')
    def test_download_streams_success(self, mock_limiter, mock_get):
        """Test successful stream download with single API call."""
        # Mock rate limiter to allow requests
        mock_limiter.check_and_wait.return_value = True

        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            'X-RateLimit-Limit': '200,2000',
            'X-RateLimit-Usage': '10,100'
        }
        mock_response.json.return_value = {
            'time': {'data': [0, 10, 20, 30]},
            'distance': {'data': [0, 100, 200, 300]},
            'altitude': {'data': [100, 110, 120, 130]},
            'grade_smooth': {'data': [0, 2, 3, 1]},
            'velocity_smooth': {'data': [3.0, 3.1, 3.2, 3.0]},
            'heartrate': {'data': [120, 125, 130, 128]},
            'cadence': {'data': [80, 82, 81, 80]},
            'moving': {'data': [True, True, True, True]}
        }
        mock_get.return_value = mock_response

        # Call download_streams
        result = download_streams(
            self.test_activity_id,
            self.test_token,
            None,
            self.test_output_dir
        )

        # Verify single API call was made
        self.assertEqual(mock_get.call_count, 1)

        # Verify correct parameters
        call_args = mock_get.call_args
        self.assertIn('keys', call_args[1]['params'])
        keys_param = call_args[1]['params']['keys']
        self.assertIn('time', keys_param)
        self.assertIn('altitude', keys_param)
        self.assertIn('distance', keys_param)

        # Verify CSV was created
        self.assertIsNotNone(result)
        self.assertTrue(os.path.exists(result))

        # Verify CSV contents
        df = pd.read_csv(result)
        self.assertEqual(len(df), 4)
        self.assertIn('time', df.columns)
        self.assertIn('altitude', df.columns)
        self.assertEqual(df['time'].iloc[0], 0)
        self.assertEqual(df['altitude'].iloc[-1], 130)

    @patch('src.strava.api.r.get')
    @patch('src.strava.api._rate_limiter')
    def test_download_streams_rate_limit_exhausted(self, mock_limiter, mock_get):
        """Test download blocked when rate limit exhausted."""
        # Mock rate limiter to block requests
        mock_limiter.check_and_wait.return_value = False

        result = download_streams(
            self.test_activity_id,
            self.test_token,
            None,
            self.test_output_dir
        )

        # Should return None without making API call
        self.assertIsNone(result)
        mock_get.assert_not_called()

    @patch('src.strava.api.r.get')
    @patch('src.strava.api._rate_limiter')
    def test_download_streams_api_error(self, mock_limiter, mock_get):
        """Test handling of API errors."""
        mock_limiter.check_and_wait.return_value = True

        # Mock API error response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.headers = {}
        mock_get.return_value = mock_response

        result = download_streams(
            self.test_activity_id,
            self.test_token,
            None,
            self.test_output_dir
        )

        # Should return None on error
        self.assertIsNone(result)

    @patch('src.strava.api.r.get')
    @patch('src.strava.api._rate_limiter')
    def test_download_streams_missing_critical_data(self, mock_limiter, mock_get):
        """Test handling of incomplete stream data."""
        mock_limiter.check_and_wait.return_value = True

        # Mock response with missing altitude data
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            'time': {'data': [0, 10, 20]},
            'distance': {'data': [0, 100, 200]},
            # Missing altitude
            'grade_smooth': {'data': []},
            'velocity_smooth': {'data': []},
            'heartrate': {'data': []},
            'cadence': {'data': []},
            'moving': {'data': []}
        }
        mock_get.return_value = mock_response

        result = download_streams(
            self.test_activity_id,
            self.test_token,
            None,
            self.test_output_dir
        )

        # Should return None when critical data missing
        self.assertIsNone(result)

    @patch('src.strava.api.r.get')
    @patch('src.strava.api._rate_limiter')
    def test_fetch_activities_pagination(self, mock_limiter, mock_get):
        """Test activity fetching with pagination."""
        mock_limiter.check_and_wait.return_value = True

        # Mock paginated responses
        page1_response = Mock()
        page1_response.status_code = 200
        page1_response.headers = {'X-RateLimit-Usage': '1,100'}
        page1_response.json.return_value = [
            {'id': 1, 'name': 'Activity 1', 'sport_type': 'Run'},
            {'id': 2, 'name': 'Activity 2', 'sport_type': 'Run'}
        ]

        page2_response = Mock()
        page2_response.status_code = 200
        page2_response.headers = {'X-RateLimit-Usage': '2,101'}
        page2_response.json.return_value = []  # No more data

        mock_get.side_effect = [page1_response, page2_response]

        activities = fetch_activities(self.test_token, 1234567890)

        # Should have fetched 2 pages
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(len(activities), 2)
        self.assertEqual(activities[0]['id'], 1)

    @patch('src.strava.api.r.get')
    @patch('src.strava.api._rate_limiter')
    def test_fetch_activities_sport_filter(self, mock_limiter, mock_get):
        """Test filtering activities by sport type."""
        mock_limiter.check_and_wait.return_value = True

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = [
            {'id': 1, 'sport_type': 'Run'},
            {'id': 2, 'sport_type': 'Ride'},
            {'id': 3, 'sport_type': 'Run'},
            {'id': 4, 'sport_type': 'Swim'}
        ]

        # Second call returns empty
        empty_response = Mock()
        empty_response.status_code = 200
        empty_response.headers = {}
        empty_response.json.return_value = []

        mock_get.side_effect = [mock_response, empty_response]

        activities = fetch_activities(self.test_token, 0, sport_type='Run')

        # Should only return Run activities
        self.assertEqual(len(activities), 2)
        self.assertTrue(all(a['sport_type'] == 'Run' for a in activities))

    def test_get_rate_limit_status(self):
        """Test rate limit status retrieval."""
        status = get_rate_limit_status()

        # Should return dictionary with expected keys
        self.assertIn('short_usage', status)
        self.assertIn('short_limit', status)
        self.assertIn('daily_usage', status)
        self.assertIn('daily_limit', status)
        self.assertIn('short_remaining', status)
        self.assertIn('daily_remaining', status)


if __name__ == '__main__':
    unittest.main()
