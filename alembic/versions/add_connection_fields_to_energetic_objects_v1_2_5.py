"""add connection fields to energetic_objects v1.2.5

Revision ID: add_connection_v125
Revises: add_timezone_v124
Create Date: 2025-11-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_connection_v125'
down_revision: Union[str, None] = 'add_timezone_v124'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем новые поля для подключения к энергетическим объектам
    op.add_column('energetic_objects', 
        sa.Column('ip_address', sa.String(), 
                  nullable=True,
                  comment='IP-адрес объекта'))
    
    op.add_column('energetic_objects', 
        sa.Column('port', sa.Integer(), 
                  nullable=True,
                  comment='Порт объекта'))
    
    op.add_column('energetic_objects', 
        sa.Column('inverter_login', sa.String(), 
                  nullable=True,
                  comment='Логин для доступа к инвертору'))
    
    op.add_column('energetic_objects', 
        sa.Column('inverter_password', sa.String(), 
                  nullable=True,
                  comment='Пароль для доступа к инвертору'))


def downgrade() -> None:
    # Удаляем добавленные поля
    op.drop_column('energetic_objects', 'inverter_password')
    op.drop_column('energetic_objects', 'inverter_login')
    op.drop_column('energetic_objects', 'port')
    op.drop_column('energetic_objects', 'ip_address')
