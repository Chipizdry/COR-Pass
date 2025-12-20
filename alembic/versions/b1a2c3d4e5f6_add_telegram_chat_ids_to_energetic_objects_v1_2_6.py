"""add telegram_chat_ids to energetic_objects

Revision ID: b1a2c3d4e5f6
Revises: d67798347eaf
Create Date: 2025-12-01
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b1a2c3d4e5f6'
down_revision = 'd67798347eaf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('energetic_objects', sa.Column('telegram_chat_ids', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('energetic_objects', 'telegram_chat_ids')
