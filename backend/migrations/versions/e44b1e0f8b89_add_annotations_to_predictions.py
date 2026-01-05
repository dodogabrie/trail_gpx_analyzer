"""add_annotations_to_predictions

Revision ID: e44b1e0f8b89
Revises: 3966644a58f3
Create Date: 2026-01-01 16:50:37.574395

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e44b1e0f8b89'
down_revision = '3966644a58f3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('predictions', sa.Column('annotations', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('predictions', 'annotations')
