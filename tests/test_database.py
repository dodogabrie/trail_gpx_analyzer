import unittest
import os
import sqlite3
from src.database import Database, init_database


class TestDatabase(unittest.TestCase):
    """Test database schema and operations."""

    def setUp(self):
        """Create test database."""
        self.test_db_path = "tests/test_gpx.db"
        # Remove test db if exists
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

        self.db = Database(self.test_db_path)

    def tearDown(self):
        """Clean up test database."""
        self.db.close()
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_database_creation(self):
        """Test database file is created."""
        self.assertTrue(os.path.exists(self.test_db_path))

    def test_tables_created(self):
        """Test all required tables are created."""
        cursor = self.db.conn.cursor()

        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        # Verify all expected tables exist
        expected_tables = ['users', 'activities', 'streams', 'user_clusters', 'segments']
        for table in expected_tables:
            self.assertIn(table, tables, f"Table {table} not found")

    def test_users_table_schema(self):
        """Test users table has correct columns."""
        cursor = self.db.conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        self.assertIn('id', columns)
        self.assertIn('strava_id', columns)
        self.assertIn('username', columns)
        self.assertIn('firstname', columns)
        self.assertIn('lastname', columns)
        self.assertIn('created_at', columns)
        self.assertIn('updated_at', columns)

    def test_activities_table_schema(self):
        """Test activities table has correct columns."""
        cursor = self.db.conn.cursor()
        cursor.execute("PRAGMA table_info(activities)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        required_columns = [
            'id', 'user_id', 'strava_id', 'name', 'sport_type',
            'start_date', 'distance', 'moving_time', 'elapsed_time',
            'total_elevation_gain', 'average_speed', 'max_speed',
            'has_streams', 'created_at'
        ]

        for col in required_columns:
            self.assertIn(col, columns, f"Column {col} not found in activities table")

    def test_streams_table_schema(self):
        """Test streams table has correct columns."""
        cursor = self.db.conn.cursor()
        cursor.execute("PRAGMA table_info(streams)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        required_columns = [
            'id', 'activity_id', 'time_array', 'distance_array',
            'altitude_array', 'grade_smooth_array', 'velocity_smooth_array',
            'heartrate_array', 'cadence_array', 'moving_array'
        ]

        for col in required_columns:
            self.assertIn(col, columns, f"Column {col} not found in streams table")

    def test_user_clusters_table_schema(self):
        """Test user_clusters table has correct columns."""
        cursor = self.db.conn.cursor()
        cursor.execute("PRAGMA table_info(user_clusters)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        required_columns = [
            'id', 'user_id', 'cluster_id', 'vam_avg', 'pace_avg',
            'distance_preference', 'activities_count', 'total_distance',
            'total_elevation_gain'
        ]

        for col in required_columns:
            self.assertIn(col, columns, f"Column {col} not found in user_clusters table")

    def test_segments_table_schema(self):
        """Test segments table has correct columns."""
        cursor = self.db.conn.cursor()
        cursor.execute("PRAGMA table_info(segments)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        required_columns = [
            'id', 'activity_id', 'start_idx', 'end_idx', 'distance',
            'duration', 'elevation_gain', 'elevation_loss', 'avg_slope',
            'avg_pace', 'cumulative_distance', 'cumulative_elevation_gain'
        ]

        for col in required_columns:
            self.assertIn(col, columns, f"Column {col} not found in segments table")

    def test_indexes_created(self):
        """Test indexes are created for performance."""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]

        # Check some key indexes exist
        expected_indexes = [
            'idx_activities_user_id',
            'idx_activities_strava_id',
            'idx_streams_activity_id',
            'idx_segments_activity_id'
        ]

        for idx in expected_indexes:
            self.assertIn(idx, indexes, f"Index {idx} not found")

    def test_foreign_key_constraints(self):
        """Test foreign key relationships work."""
        cursor = self.db.conn.cursor()

        # Insert test user
        cursor.execute("""
            INSERT INTO users (strava_id, username)
            VALUES (12345, 'testuser')
        """)
        user_id = cursor.lastrowid

        # Insert test activity
        cursor.execute("""
            INSERT INTO activities (user_id, strava_id, name, sport_type, distance)
            VALUES (?, 67890, 'Test Run', 'Run', 10000)
        """, (user_id,))
        activity_id = cursor.lastrowid

        self.db.conn.commit()

        # Verify data inserted
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        self.assertIsNotNone(user)

        cursor.execute("SELECT * FROM activities WHERE id = ?", (activity_id,))
        activity = cursor.fetchone()
        self.assertIsNotNone(activity)

    def test_unique_constraints(self):
        """Test unique constraints work."""
        cursor = self.db.conn.cursor()

        # Insert user
        cursor.execute("""
            INSERT INTO users (strava_id, username)
            VALUES (12345, 'testuser')
        """)
        self.db.conn.commit()

        # Try to insert duplicate strava_id
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO users (strava_id, username)
                VALUES (12345, 'duplicate')
            """)
            self.db.conn.commit()

    def test_context_manager(self):
        """Test database works as context manager."""
        db_path = "tests/test_context.db"

        with Database(db_path) as db:
            cursor = db.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            self.assertGreater(len(tables), 0)

        # Database should be closed
        # Clean up
        if os.path.exists(db_path):
            os.remove(db_path)

    def test_init_database_function(self):
        """Test init_database helper function."""
        db_path = "tests/test_init.db"
        db = init_database(db_path)

        self.assertIsInstance(db, Database)
        self.assertTrue(os.path.exists(db_path))

        db.close()
        if os.path.exists(db_path):
            os.remove(db_path)

    def test_cascade_delete(self):
        """Test cascade delete on foreign keys."""
        cursor = self.db.conn.cursor()

        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")

        # Insert user and activity
        cursor.execute("INSERT INTO users (strava_id, username) VALUES (99999, 'testuser')")
        user_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO activities (user_id, strava_id, name, sport_type)
            VALUES (?, 88888, 'Test Activity', 'Run')
        """, (user_id,))
        activity_id = cursor.lastrowid

        self.db.conn.commit()

        # Delete user
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.db.conn.commit()

        # Activity should be deleted too (CASCADE)
        cursor.execute("SELECT * FROM activities WHERE id = ?", (activity_id,))
        result = cursor.fetchone()
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
