import unittest
from datetime import datetime, timedelta
from src.strava.rate_limiter import RateLimiter


class TestRateLimiter(unittest.TestCase):
    """Test RateLimiter quota tracking and enforcement."""

    def setUp(self):
        """Create fresh rate limiter for each test."""
        self.limiter = RateLimiter(short_limit=10, daily_limit=100)

    def test_initialization(self):
        """Test rate limiter initializes with correct limits."""
        self.assertEqual(self.limiter.short_limit, 10)
        self.assertEqual(self.limiter.daily_limit, 100)
        self.assertEqual(self.limiter.short_usage, 0)
        self.assertEqual(self.limiter.daily_usage, 0)

    def test_increment(self):
        """Test usage counter increments correctly."""
        self.limiter.increment()
        self.assertEqual(self.limiter.short_usage, 1)
        self.assertEqual(self.limiter.daily_usage, 1)

        self.limiter.increment(5)
        self.assertEqual(self.limiter.short_usage, 6)
        self.assertEqual(self.limiter.daily_usage, 6)

    def test_update_from_headers(self):
        """Test parsing Strava API response headers."""
        headers = {
            'X-RateLimit-Limit': '200,2000',
            'X-RateLimit-Usage': '50,500'
        }
        self.limiter.update_from_headers(headers)

        self.assertEqual(self.limiter.short_limit, 200)
        self.assertEqual(self.limiter.daily_limit, 2000)
        self.assertEqual(self.limiter.short_usage, 50)
        self.assertEqual(self.limiter.daily_usage, 500)

    def test_update_from_headers_invalid(self):
        """Test handling invalid or missing headers."""
        # Missing headers - should not crash
        self.limiter.update_from_headers({})
        self.assertEqual(self.limiter.short_limit, 10)  # Unchanged

        # Malformed headers
        self.limiter.update_from_headers({'X-RateLimit-Limit': 'invalid'})
        self.assertEqual(self.limiter.short_limit, 10)  # Unchanged

    def test_check_and_wait_within_limits(self):
        """Test request proceeds when within limits."""
        self.limiter.short_usage = 5
        self.limiter.daily_usage = 50

        result = self.limiter.check_and_wait()
        self.assertTrue(result)

    def test_check_and_wait_daily_limit_reached(self):
        """Test request blocked when daily limit reached."""
        self.limiter.daily_usage = 100

        result = self.limiter.check_and_wait()
        self.assertFalse(result)

    def test_check_and_wait_near_daily_limit(self):
        """Test request blocked when exceeding daily limit."""
        self.limiter.daily_usage = 99

        # Requesting 2 would exceed limit
        result = self.limiter.check_and_wait(requests_needed=2)
        self.assertFalse(result)

    def test_window_reset(self):
        """Test usage resets after window expires."""
        # Set past reset times
        self.limiter.short_usage = 10
        self.limiter.daily_usage = 100
        self.limiter.short_reset_time = datetime.now() - timedelta(seconds=1)
        self.limiter.daily_reset_time = datetime.now() - timedelta(seconds=1)

        result = self.limiter.check_and_wait()
        self.assertTrue(result)
        self.assertEqual(self.limiter.short_usage, 0)
        self.assertEqual(self.limiter.daily_usage, 0)

    def test_get_status(self):
        """Test status dictionary returns correct information."""
        self.limiter.short_usage = 7
        self.limiter.daily_usage = 63

        status = self.limiter.get_status()

        self.assertEqual(status['short_usage'], 7)
        self.assertEqual(status['short_limit'], 10)
        self.assertEqual(status['short_remaining'], 3)
        self.assertEqual(status['daily_usage'], 63)
        self.assertEqual(status['daily_limit'], 100)
        self.assertEqual(status['daily_remaining'], 37)

        # Time-based values should be positive
        self.assertGreater(status['short_reset_in_seconds'], 0)
        self.assertGreater(status['daily_reset_in_hours'], 0)

    def test_multiple_requests_tracking(self):
        """Test tracking multiple sequential requests."""
        for i in range(5):
            self.assertTrue(self.limiter.check_and_wait())
            self.limiter.increment()

        self.assertEqual(self.limiter.short_usage, 5)
        self.assertEqual(self.limiter.daily_usage, 5)

    def test_print_status(self):
        """Test print_status doesn't crash."""
        self.limiter.short_usage = 3
        self.limiter.daily_usage = 25

        # Should not raise exception
        try:
            self.limiter.print_status()
            success = True
        except Exception:
            success = False

        self.assertTrue(success)


if __name__ == '__main__':
    unittest.main()
