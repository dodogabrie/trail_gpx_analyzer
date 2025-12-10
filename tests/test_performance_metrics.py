import unittest
import pandas as pd
import numpy as np
from src.utils.performance_metrics import (
    calculate_vam,
    calculate_pace,
    calculate_speed,
    calculate_segment_vam,
    calculate_activity_stats,
    calculate_user_features
)


class TestPerformanceMetrics(unittest.TestCase):
    """Test performance metric calculations."""

    def test_calculate_vam(self):
        """Test VAM calculation."""
        # 1000m elevation in 1 hour = 1000 VAM
        vam = calculate_vam(elevation_gain=1000, elapsed_time=3600)
        self.assertEqual(vam, 1000)

        # 500m elevation in 30 minutes = 1000 VAM
        vam = calculate_vam(elevation_gain=500, elapsed_time=1800)
        self.assertEqual(vam, 1000)

        # 200m in 10 minutes = 1200 VAM
        vam = calculate_vam(elevation_gain=200, elapsed_time=600)
        self.assertEqual(vam, 1200)

    def test_calculate_vam_edge_cases(self):
        """Test VAM with edge cases."""
        # Zero elevation
        vam = calculate_vam(elevation_gain=0, elapsed_time=3600)
        self.assertEqual(vam, 0)

        # Zero time should raise error
        with self.assertRaises(ValueError):
            calculate_vam(elevation_gain=1000, elapsed_time=0)

        # Negative time should raise error
        with self.assertRaises(ValueError):
            calculate_vam(elevation_gain=1000, elapsed_time=-100)

    def test_calculate_pace(self):
        """Test pace calculation."""
        # 5km in 30 minutes = 6 min/km
        pace = calculate_pace(distance=5000, elapsed_time=1800, unit='min/km')
        self.assertAlmostEqual(pace, 6.0, places=2)

        # 10km in 50 minutes = 5 min/km
        pace = calculate_pace(distance=10000, elapsed_time=3000, unit='min/km')
        self.assertAlmostEqual(pace, 5.0, places=2)

    def test_calculate_pace_miles(self):
        """Test pace calculation in min/mile."""
        # ~1.6km in 8 minutes = ~5 min/mi
        pace = calculate_pace(distance=1609.34, elapsed_time=480, unit='min/mi')
        self.assertAlmostEqual(pace, 5.0, places=1)

    def test_calculate_pace_edge_cases(self):
        """Test pace with edge cases."""
        # Zero distance
        with self.assertRaises(ValueError):
            calculate_pace(distance=0, elapsed_time=3600)

        # Invalid unit
        with self.assertRaises(ValueError):
            calculate_pace(distance=5000, elapsed_time=1800, unit='min/yard')

    def test_calculate_speed(self):
        """Test speed calculation."""
        # 10km in 1 hour = 10 km/h
        speed = calculate_speed(distance=10000, elapsed_time=3600)
        self.assertAlmostEqual(speed, 10.0, places=2)

        # 5km in 30 minutes = 10 km/h
        speed = calculate_speed(distance=5000, elapsed_time=1800)
        self.assertAlmostEqual(speed, 10.0, places=2)

    def test_calculate_segment_vam(self):
        """Test VAM calculation for activity segment."""
        # Create test DataFrame
        df = pd.DataFrame({
            'time': [0, 60, 120, 180, 240, 300],
            'altitude': [100, 110, 115, 120, 130, 135],
            'distance': [0, 100, 200, 300, 400, 500]
        })

        # Segment from index 0 to 4 (4 minutes, 30m gain)
        # 30m / 240s * 3600 = 450 VAM
        vam = calculate_segment_vam(df, start_idx=0, end_idx=4)
        self.assertGreater(vam, 0)

        # Full activity segment
        vam = calculate_segment_vam(df, start_idx=0, end_idx=len(df))
        self.assertGreater(vam, 0)

    def test_calculate_segment_vam_flat(self):
        """Test VAM for flat segment."""
        df = pd.DataFrame({
            'time': [0, 60, 120],
            'altitude': [100, 100, 100]
        })

        vam = calculate_segment_vam(df, start_idx=0, end_idx=3)
        self.assertEqual(vam, 0.0)

    def test_calculate_segment_vam_invalid(self):
        """Test segment VAM with invalid inputs."""
        df = pd.DataFrame({
            'time': [0, 60, 120],
            'altitude': [100, 110, 120]
        })

        # Invalid indices
        with self.assertRaises(ValueError):
            calculate_segment_vam(df, start_idx=2, end_idx=1)

        with self.assertRaises(ValueError):
            calculate_segment_vam(df, start_idx=-1, end_idx=2)

    def test_calculate_activity_stats(self):
        """Test comprehensive activity statistics."""
        df = pd.DataFrame({
            'time': [0, 60, 120, 180, 240, 300],
            'distance': [0, 100, 250, 450, 700, 1000],
            'altitude': [100, 110, 105, 120, 115, 125]
        })

        stats = calculate_activity_stats(df)

        # Check all expected keys
        self.assertIn('total_distance', stats)
        self.assertIn('duration', stats)
        self.assertIn('elevation_gain', stats)
        self.assertIn('elevation_loss', stats)
        self.assertIn('avg_pace', stats)
        self.assertIn('avg_speed', stats)
        self.assertIn('vam', stats)
        self.assertIn('max_altitude', stats)
        self.assertIn('min_altitude', stats)

        # Verify values
        self.assertEqual(stats['total_distance'], 1000)
        self.assertEqual(stats['duration'], 300)
        self.assertEqual(stats['max_altitude'], 125)
        self.assertEqual(stats['min_altitude'], 100)
        self.assertGreater(stats['elevation_gain'], 0)
        self.assertGreater(stats['elevation_loss'], 0)
        self.assertGreater(stats['avg_speed'], 0)

    def test_calculate_activity_stats_empty(self):
        """Test stats calculation with empty DataFrame."""
        df = pd.DataFrame({
            'time': [],
            'distance': [],
            'altitude': []
        })

        stats = calculate_activity_stats(df)
        self.assertEqual(stats['total_distance'], 0)
        self.assertEqual(stats['duration'], 0)

    def test_calculate_user_features_empty(self):
        """Test user features with no activities."""
        features = calculate_user_features([])

        self.assertEqual(features['vam_avg'], 0)
        self.assertEqual(features['pace_avg'], 0)
        self.assertEqual(features['activities_count'], 0)
        self.assertEqual(features['distance_preference'], 'unknown')

    def test_calculate_user_features_short_distance(self):
        """Test user features for short distance runner."""
        activities = [
            {'distance': 5000, 'moving_time': 1800, 'total_elevation_gain': 50},
            {'distance': 8000, 'moving_time': 2800, 'total_elevation_gain': 80},
            {'distance': 6000, 'moving_time': 2100, 'total_elevation_gain': 60}
        ]

        features = calculate_user_features(activities)

        self.assertEqual(features['activities_count'], 3)
        self.assertEqual(features['distance_preference'], 'short')
        self.assertGreater(features['vam_avg'], 0)
        self.assertGreater(features['pace_avg'], 0)
        self.assertEqual(features['total_distance'], 19000)

    def test_calculate_user_features_medium_distance(self):
        """Test user features for medium distance runner."""
        activities = [
            {'distance': 15000, 'moving_time': 5400, 'total_elevation_gain': 200},
            {'distance': 18000, 'moving_time': 6300, 'total_elevation_gain': 250}
        ]

        features = calculate_user_features(activities)
        self.assertEqual(features['distance_preference'], 'medium')

    def test_calculate_user_features_long_distance(self):
        """Test user features for long distance runner."""
        activities = [
            {'distance': 30000, 'moving_time': 10800, 'total_elevation_gain': 500},
            {'distance': 35000, 'moving_time': 12600, 'total_elevation_gain': 600}
        ]

        features = calculate_user_features(activities)
        self.assertEqual(features['distance_preference'], 'long')

    def test_calculate_user_features_ultra_distance(self):
        """Test user features for ultra runner."""
        activities = [
            {'distance': 55000, 'moving_time': 21600, 'total_elevation_gain': 1500},
            {'distance': 80000, 'moving_time': 32400, 'total_elevation_gain': 2500}
        ]

        features = calculate_user_features(activities)
        self.assertEqual(features['distance_preference'], 'ultra')
        self.assertGreater(features['vam_avg'], 0)

    def test_calculate_user_features_mixed_activities(self):
        """Test user features with varied activities."""
        activities = [
            {'distance': 5000, 'moving_time': 1500, 'total_elevation_gain': 100},
            {'distance': 10000, 'moving_time': 3000, 'total_elevation_gain': 0},  # Flat run
            {'distance': 15000, 'moving_time': 5400, 'total_elevation_gain': 300},
            {'distance': 0, 'moving_time': 0, 'total_elevation_gain': 0}  # Invalid
        ]

        features = calculate_user_features(activities)

        # Should handle invalid activity gracefully
        self.assertEqual(features['activities_count'], 4)
        self.assertGreater(features['total_distance'], 0)

        # VAM should only count activities with elevation
        self.assertGreater(features['vam_avg'], 0)


if __name__ == '__main__':
    unittest.main()
