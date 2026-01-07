"""add_auto_prediction_fields_to_gpx_files

Revision ID: 3fc363b813d7
Revises: e44b1e0f8b89
Create Date: 2026-01-05 23:26:57.155667

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3fc363b813d7'
down_revision = 'e44b1e0f8b89'
branch_labels = None
depends_on = None


def upgrade():
    # Add auto-prediction status fields to gpx_files table
    # Note: No FK constraint for SQLite simplicity (app-level relationship only)

    # Check if columns exist before adding (handles partial migrations)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('gpx_files')]

    if 'processing_status' not in columns:
        op.add_column('gpx_files', sa.Column('processing_status', sa.String(length=50), server_default='pending', nullable=True))
    if 'prediction_id' not in columns:
        op.add_column('gpx_files', sa.Column('prediction_id', sa.Integer(), nullable=True))
    if 'error_message' not in columns:
        op.add_column('gpx_files', sa.Column('error_message', sa.Text(), nullable=True))


def downgrade():
    # Remove columns if they exist
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('gpx_files')]

    if 'error_message' in columns:
        op.drop_column('gpx_files', 'error_message')
    if 'prediction_id' in columns:
        op.drop_column('gpx_files', 'prediction_id')
    if 'processing_status' in columns:
        op.drop_column('gpx_files', 'processing_status')
