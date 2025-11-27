"""add_protocol_to_energetic_objects_v1_3_1

Revision ID: c107213c329f
Revises: add_corporate_clients_v1_3_0
Create Date: 2025-11-12 15:42:42.762076

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c107213c329f'
down_revision: Union[str, None] = 'add_corporate_clients_v1_3_0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем поле protocol к таблице energetic_objects
    op.add_column(
        'energetic_objects',
        sa.Column('protocol', sa.String(), nullable=True, comment='Протокол связи (modbus, http, mqtt и т.д.)')
    )


def downgrade() -> None:
    # Удаляем поле protocol из таблицы energetic_objects
    op.drop_column('energetic_objects', 'protocol')
