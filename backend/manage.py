#!/usr/bin/env python3
"""Database migration management script.

Usage:
    python manage.py db init       # Initialize migrations (first time only)
    python manage.py db migrate    # Generate new migration
    python manage.py db upgrade    # Apply migrations
    python manage.py db downgrade  # Rollback migration
    python manage.py db history    # Show migration history
    python manage.py db current    # Show current revision
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask_migrate import Migrate, MigrateCommand
from flask.cli import FlaskGroup
from app import create_app
from database import db

app = create_app()
migrate = Migrate(app, db)


def create_cli():
    """Create Flask CLI with db commands."""
    from flask.cli import FlaskGroup

    cli = FlaskGroup(create_app=lambda: app)

    @cli.command()
    def init_db():
        """Initialize the database (create all tables)."""
        with app.app_context():
            db.create_all()
            print("✓ Database initialized!")

    @cli.command()
    def drop_db():
        """Drop all database tables (DANGEROUS!)."""
        with app.app_context():
            confirm = input("Are you sure you want to drop all tables? (yes/no): ")
            if confirm.lower() == 'yes':
                db.drop_all()
                print("✓ All tables dropped!")
            else:
                print("Cancelled.")

    return cli


if __name__ == '__main__':
    # Use Flask-Migrate commands
    from flask_migrate import init, migrate as mig, upgrade, downgrade, history, current

    import argparse
    parser = argparse.ArgumentParser(description='Database migration commands')
    parser.add_argument('command', choices=['init', 'migrate', 'upgrade', 'downgrade', 'history', 'current', 'init-db', 'drop-db'],
                       help='Migration command to run')
    parser.add_argument('-m', '--message', help='Migration message', default=None)

    args = parser.parse_args()

    with app.app_context():
        if args.command == 'init':
            print("Initializing migrations...")
            os.system('flask db init')
        elif args.command == 'migrate':
            message = args.message or 'Auto-generated migration'
            print(f"Generating migration: {message}")
            os.system(f'flask db migrate -m "{message}"')
        elif args.command == 'upgrade':
            print("Applying migrations...")
            os.system('flask db upgrade')
        elif args.command == 'downgrade':
            print("Rolling back migration...")
            os.system('flask db downgrade')
        elif args.command == 'history':
            os.system('flask db history')
        elif args.command == 'current':
            os.system('flask db current')
        elif args.command == 'init-db':
            db.create_all()
            print("✓ Database initialized!")
        elif args.command == 'drop-db':
            confirm = input("Are you sure you want to drop all tables? (yes/no): ")
            if confirm.lower() == 'yes':
                db.drop_all()
                print("✓ All tables dropped!")
