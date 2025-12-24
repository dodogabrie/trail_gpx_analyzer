"""Add fatigue_curve column to performance_snapshots table.

Run with: python migrations/add_fatigue_curve.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db
from app import create_app

def migrate():
    """Add fatigue_curve column."""
    app = create_app()
    with app.app_context():
        # Check if column already exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('performance_snapshots')]

        if 'fatigue_curve' in columns:
            print("✓ Column 'fatigue_curve' already exists")
            return

        # Add column
        print("Adding 'fatigue_curve' column to performance_snapshots...")
        db.engine.execute(
            "ALTER TABLE performance_snapshots ADD COLUMN fatigue_curve TEXT"
        )
        print("✓ Migration complete")

if __name__ == '__main__':
    migrate()
