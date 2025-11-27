"""add timezone to energetic_objects v1.2.4

Revision ID: add_timezone_v124
Revises: fix_cor_id_unique
Create Date: 2025-11-03 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_timezone_v124'
down_revision: Union[str, None] = 'fix_cor_id_unique'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Шаг 1: Добавляем поле timezone как nullable
    op.add_column('energetic_objects', 
        sa.Column('timezone', sa.String(), 
                  nullable=True,
                  comment='Часовой пояс объекта (например: Europe/Kiev, America/New_York)'))
    
    # Шаг 2: Заполняем значением 'Europe/Kiev' для всех существующих объектов
    op.execute("UPDATE energetic_objects SET timezone = 'Europe/Kiev' WHERE timezone IS NULL")
    
    # Шаг 3: Делаем поле NOT NULL с дефолтным значением
    op.alter_column('energetic_objects', 'timezone',
                    nullable=False,
                    server_default='Europe/Kiev')


def downgrade() -> None:
    # Удаляем поле timezone
    op.drop_column('energetic_objects', 'timezone')
