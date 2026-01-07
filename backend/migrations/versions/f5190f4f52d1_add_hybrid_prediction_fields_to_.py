"""add hybrid prediction fields to predictions table

Revision ID: f5190f4f52d1
Revises: dc8f482ceef3
Create Date: 2026-01-05 23:53:08.955738

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f5190f4f52d1'
down_revision = 'dc8f482ceef3'
branch_labels = None
depends_on = None


def upgrade():
    # Add new hybrid prediction fields
    op.add_column('predictions', sa.Column('tier', sa.Integer(), nullable=True))
    op.add_column('predictions', sa.Column('effort_level', sa.String(length=50), nullable=True))
    op.add_column('predictions', sa.Column('prediction_data', sa.JSON(), nullable=True))

    # SQLite: alter column requires batch operations
    with op.batch_alter_table('predictions', schema=None) as batch_op:
        batch_op.alter_column('flat_pace', existing_type=sa.Float(), nullable=True)
        batch_op.alter_column('total_time_seconds', existing_type=sa.Float(), nullable=True)
        batch_op.alter_column('predicted_segments', existing_type=sa.JSON(), nullable=True)


def downgrade():
    # SQLite: alter column requires batch operations
    with op.batch_alter_table('predictions', schema=None) as batch_op:
        batch_op.alter_column('predicted_segments', existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column('total_time_seconds', existing_type=sa.Float(), nullable=False)
        batch_op.alter_column('flat_pace', existing_type=sa.Float(), nullable=False)

    # Remove new fields
    op.drop_column('predictions', 'prediction_data')
    op.drop_column('predictions', 'effort_level')
    op.drop_column('predictions', 'tier')
