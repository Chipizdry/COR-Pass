"""add fuel station tables v1.2.7

Revision ID: add_fuel_station_v127
Revises: add_financier_v126
Create Date: 2025-11-06 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_fuel_station_v127'
down_revision: Union[str, None] = 'add_financier_v126'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создание таблицы сессий QR кодов для заправок
    op.create_table(
        'fuel_station_qr_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_cor_id', sa.String(36), nullable=False),
        sa.Column('session_token', sa.String(255), nullable=False, unique=True),
        sa.Column('totp_code', sa.String(10), nullable=False),
        sa.Column('timestamp_token', sa.String(255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False, default=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_cor_id'], ['users.cor_id'], ondelete='CASCADE'),
    )
    
    # Создание индексов для fuel_station_qr_sessions
    op.create_index('ix_fuel_qr_user_cor_id', 'fuel_station_qr_sessions', ['user_cor_id'])
    op.create_index('ix_fuel_qr_session_token', 'fuel_station_qr_sessions', ['session_token'])
    op.create_index('ix_fuel_qr_expires_at', 'fuel_station_qr_sessions', ['expires_at'])
    op.create_index('ix_fuel_qr_is_used', 'fuel_station_qr_sessions', ['is_used'])
    
    # Создание таблицы конфигурации для интеграции с финансовым бэкендом
    op.create_table(
        'finance_backend_auth',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('service_name', sa.String(100), nullable=False, unique=True),
        sa.Column('api_endpoint', sa.String(500), nullable=False),
        sa.Column('totp_secret', sa.LargeBinary(), nullable=False),
        sa.Column('totp_interval', sa.Integer(), nullable=False, default=30),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('last_successful_auth', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_failed_auth', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_attempts', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # Создание индексов для finance_backend_auth
    op.create_index('ix_finance_backend_is_active', 'finance_backend_auth', ['is_active'])
    op.create_index('ix_finance_backend_service_name', 'finance_backend_auth', ['service_name'])


def downgrade() -> None:

    op.drop_index('ix_finance_backend_service_name', table_name='finance_backend_auth')
    op.drop_index('ix_finance_backend_is_active', table_name='finance_backend_auth')
    

    op.drop_table('finance_backend_auth')
    

    op.drop_index('ix_fuel_qr_is_used', table_name='fuel_station_qr_sessions')
    op.drop_index('ix_fuel_qr_expires_at', table_name='fuel_station_qr_sessions')
    op.drop_index('ix_fuel_qr_session_token', table_name='fuel_station_qr_sessions')
    op.drop_index('ix_fuel_qr_user_cor_id', table_name='fuel_station_qr_sessions')
    

    op.drop_table('fuel_station_qr_sessions')
