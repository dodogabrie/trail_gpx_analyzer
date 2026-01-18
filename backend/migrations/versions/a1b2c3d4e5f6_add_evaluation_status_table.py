"""add_evaluation_status_table

Revision ID: a1b2c3d4e5f6
Revises: f5190f4f52d1
Create Date: 2026-01-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f5190f4f52d1'
branch_labels = None
depends_on = None


def upgrade():
    # Create evaluation_status table
    op.create_table('evaluation_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='idle', nullable=False),
        sa.Column('current_step', sa.String(length=100), nullable=True),
        sa.Column('total_steps', sa.Integer(), server_default='6', nullable=True),
        sa.Column('current_step_number', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_activities', sa.Integer(), server_default='0', nullable=True),
        sa.Column('training_activities', sa.Integer(), server_default='0', nullable=True),
        sa.Column('target_activity_id', sa.String(length=50), nullable=True),
        sa.Column('target_activity_name', sa.String(length=255), nullable=True),
        sa.Column('total_segments', sa.Integer(), server_default='0', nullable=True),
        sa.Column('processed_segments', sa.Integer(), server_default='0', nullable=True),
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
    op.drop_table('evaluation_status')
