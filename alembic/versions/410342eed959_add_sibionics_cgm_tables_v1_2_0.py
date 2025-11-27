"""add_sibionics_cgm_tables_v1_2_0

Revision ID: 410342eed959
Revises: 74ff250d3ffc
Create Date: 2025-10-27 14:33:58.984569

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '410342eed959'
down_revision: Union[str, None] = '74ff250d3ffc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создание таблицы sibionics_auth
    op.create_table(
        'sibionics_auth',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('biz_id', sa.String(length=255), nullable=False),
        sa.Column('access_token', sa.String(length=500), nullable=True),
        sa.Column('expires_in', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('biz_id')
    )
    op.create_index('idx_sibionics_auth_user_id', 'sibionics_auth', ['user_id'], unique=False)
    op.create_index('idx_sibionics_auth_biz_id', 'sibionics_auth', ['biz_id'], unique=False)

    # Создание таблицы sibionics_devices
    op.create_table(
        'sibionics_devices',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('auth_id', sa.String(length=36), nullable=False),
        sa.Column('device_id', sa.String(length=255), nullable=False),
        sa.Column('device_name', sa.String(length=255), nullable=True),
        sa.Column('bluetooth_num', sa.String(length=255), nullable=True),
        sa.Column('serial_no', sa.String(length=255), nullable=True),
        sa.Column('status', sa.Integer(), nullable=True),
        sa.Column('current_index', sa.Integer(), nullable=True),
        sa.Column('max_index', sa.Integer(), nullable=True),
        sa.Column('min_index', sa.Integer(), nullable=True),
        sa.Column('data_gap', sa.Integer(), nullable=True),
        sa.Column('enable_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['auth_id'], ['sibionics_auth.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('auth_id', 'device_id', name='uq_auth_device')
    )
    op.create_index('idx_sibionics_device_auth_id', 'sibionics_devices', ['auth_id'], unique=False)
    op.create_index('idx_sibionics_device_device_id', 'sibionics_devices', ['device_id'], unique=False)

    # Создание таблицы sibionics_glucose
    op.create_table(
        'sibionics_glucose',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('device_id', sa.String(length=36), nullable=False),
        sa.Column('index', sa.Integer(), nullable=False),
        sa.Column('glucose_value', sa.Float(), nullable=False),
        sa.Column('trend', sa.Integer(), nullable=True),
        sa.Column('alarm_status', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['device_id'], ['sibionics_devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_id', 'index', name='uq_device_index')
    )
    op.create_index('idx_sibionics_glucose_device_id', 'sibionics_glucose', ['device_id'], unique=False)
    op.create_index('idx_sibionics_glucose_timestamp', 'sibionics_glucose', ['timestamp'], unique=False)


def downgrade() -> None:
    # Удаление таблиц в обратном порядке
    op.drop_index('idx_sibionics_glucose_timestamp', table_name='sibionics_glucose')
    op.drop_index('idx_sibionics_glucose_device_id', table_name='sibionics_glucose')
    op.drop_table('sibionics_glucose')
    
    op.drop_index('idx_sibionics_device_device_id', table_name='sibionics_devices')
    op.drop_index('idx_sibionics_device_auth_id', table_name='sibionics_devices')
    op.drop_table('sibionics_devices')
    
    op.drop_index('idx_sibionics_auth_biz_id', table_name='sibionics_auth')
    op.drop_index('idx_sibionics_auth_user_id', table_name='sibionics_auth')
    op.drop_table('sibionics_auth')
