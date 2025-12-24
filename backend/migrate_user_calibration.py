#!/usr/bin/env python3
"""Database migration to add user calibration profile columns.

Adds saved_flat_pace, saved_anchor_ratios, calibration_updated_at, and
calibration_activity_id to the users table for storing user-edited pace curves.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db
from app import create_app

def migrate():
    """Run migration to add calibration columns to users table."""
    app = create_app()
    with app.app_context():
        print("Running migration: Add user calibration profile columns")

        # SQLite doesn't support adding columns with JSON type directly in some versions
        # We'll use TEXT for JSON storage which SQLAlchemy handles automatically

        migrations = [
            "ALTER TABLE users ADD COLUMN saved_flat_pace FLOAT",
            "ALTER TABLE users ADD COLUMN saved_anchor_ratios TEXT",  # JSON stored as TEXT
            "ALTER TABLE users ADD COLUMN calibration_updated_at TIMESTAMP",
            "ALTER TABLE users ADD COLUMN calibration_activity_id INTEGER"
        ]

        for sql in migrations:
            try:
                db.session.execute(db.text(sql))
                print(f"✓ Executed: {sql}")
            except Exception as e:
                error_msg = str(e).lower()
                if 'duplicate column' in error_msg or 'already exists' in error_msg:
                    print(f"⊘ Skipped (already exists): {sql}")
                else:
                    print(f"✗ Error: {sql}")
                    print(f"  {e}")
                    raise

        db.session.commit()
        print("\n✓ Migration completed successfully!")

if __name__ == '__main__':
    migrate()
