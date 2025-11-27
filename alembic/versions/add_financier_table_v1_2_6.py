"""add financier table v1.2.6

Revision ID: add_financier_v126
Revises: add_connection_v125
Create Date: 2025-11-06 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_financier_v126'
down_revision: Union[str, None] = 'add_connection_v125'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создание таблицы финансистов
    op.create_table(
        'financiers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('financier_cor_id', sa.String(36), nullable=False, unique=True),
        sa.Column('first_name', sa.String(100), nullable=True),
        sa.Column('surname', sa.String(100), nullable=True),
        sa.Column('middle_name', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['financier_cor_id'], ['users.cor_id'], ondelete='CASCADE'),
    )
    
    # Создание индексов
    op.create_index('ix_financiers_financier_cor_id', 'financiers', ['financier_cor_id'])


def downgrade() -> None:
    # Удаление индексов
    op.drop_index('ix_financiers_financier_cor_id', table_name='financiers')
    
    # Удаление таблицы
    op.drop_table('financiers')
