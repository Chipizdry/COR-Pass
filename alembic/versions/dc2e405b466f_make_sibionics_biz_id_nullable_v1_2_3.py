"""make_sibionics_biz_id_nullable_v1_2_3

Revision ID: dc2e405b466f
Revises: ed29ac91f9f7
Create Date: 2025-11-17 11:58:08.732189

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc2e405b466f'
down_revision: Union[str, None] = 'ed29ac91f9f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Делаем biz_id nullable и убираем unique constraint
    op.alter_column('sibionics_auth', 'biz_id',
                    existing_type=sa.String(length=255),
                    nullable=True)
    
    # Убираем unique constraint с biz_id (так как может быть NULL у нескольких пользователей)
    op.drop_constraint('sibionics_auth_biz_id_key', 'sibionics_auth', type_='unique')


def downgrade() -> None:
    # Возвращаем unique constraint
    op.create_unique_constraint('sibionics_auth_biz_id_key', 'sibionics_auth', ['biz_id'])
    
    # Делаем biz_id NOT NULL
    op.alter_column('sibionics_auth', 'biz_id',
                    existing_type=sa.String(length=255),
                    nullable=False)
