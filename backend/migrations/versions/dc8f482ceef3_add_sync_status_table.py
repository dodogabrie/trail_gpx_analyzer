"""add_sync_status_table

Revision ID: dc8f482ceef3
Revises: 3fc363b813d7
Create Date: 2026-01-05 23:46:00.332687

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dc8f482ceef3'
down_revision = '3fc363b813d7'
branch_labels = None
depends_on = None


def upgrade():
    # Create sync_status table
    op.create_table('sync_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='idle', nullable=False),
        sa.Column('current_step', sa.String(length=100), nullable=True),
        sa.Column('total_activities', sa.Integer(), server_default='0', nullable=True),
        sa.Column('downloaded_activities', sa.Integer(), server_default='0', nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )


def downgrade():
    op.drop_table('sync_status')
