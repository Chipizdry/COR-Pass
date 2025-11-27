"""add corporate clients v1.3.0

Revision ID: add_corporate_clients_v1_3_0
Revises: fc213fe91ee2
Create Date: 2025-11-12 12:48:00.000000

Описание:
Добавление таблицы корпоративных клиентов для топливной системы.
Единая таблица с полем status для управления состоянием:
- pending: заявка на рассмотрении
- active: активная компания
- blocked: заблокированная компания
- rejected: отклонённая заявка

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_corporate_clients_v1_3_0'
down_revision: Union[str, None] = 'add_fuel_station_v127'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Создание таблицы корпоративных клиентов
    """
    # Создаём таблицу корпоративных клиентов
    op.create_table(
        'corporate_clients',
        sa.Column('id', sa.String(length=36), nullable=False, comment='UUID клиента'),
        sa.Column('owner_cor_id', sa.String(length=255), nullable=False, comment='COR ID владельца компании'),
        sa.Column('company_format', sa.String(length=50), nullable=False, comment='Форма підприємства (ТОВ, ФОП, ПП)'),
        sa.Column('company_name', sa.String(length=255), nullable=False, comment='Полное название компании'),
        sa.Column('address', sa.String(length=500), nullable=False, comment='Юридический адрес'),
        sa.Column('phone_number', sa.String(length=20), nullable=False, comment='Контактный телефон'),
        sa.Column('email', sa.String(length=255), nullable=False, comment='Email компании'),
        sa.Column('tax_id', sa.String(length=50), nullable=False, comment='ЄДРПОУ/ИНН'),
        
        # Статус и модерация
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending', 
                  comment='Статус: pending, active, blocked, rejected, limit_exceeded'),
        sa.Column('fuel_limit', sa.Numeric(10, 2), nullable=False, server_default='16000.00',
                  comment='Лимит компании на топливо (грн)'),
        sa.Column('reviewed_by', sa.String(length=255), nullable=True, comment='COR ID модератора'),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True, comment='Время модерации'),
        sa.Column('rejection_reason', sa.String(length=1000), nullable=True, comment='Причина отклонения/блокировки'),
        
        # Интеграция с finance backend
        sa.Column('finance_company_id', sa.Integer(), nullable=True, comment='ID компании в finance backend'),
        
        # Метаданные
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), 
                  comment='Дата создания заявки'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), 
                  onupdate=sa.text('now()'), comment='Дата последнего обновления'),
        
        # Primary key
        sa.PrimaryKeyConstraint('id', name=op.f('pk_corporate_clients')),
        
        # Foreign keys
        sa.ForeignKeyConstraint(['owner_cor_id'], ['users.cor_id'], 
                                name=op.f('fk_corporate_clients_owner_cor_id_users'), 
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.cor_id'], 
                                name=op.f('fk_corporate_clients_reviewed_by_users'), 
                                ondelete='SET NULL'),
        
        # Indexes
        sa.CheckConstraint("status IN ('pending', 'active', 'blocked', 'rejected', 'limit_exceeded')", 
                          name=op.f('ck_corporate_clients_status')),
        
        comment='Корпоративные клиенты топливной системы'
    )
    
    # Создаём индексы для быстрого поиска
    op.create_index(op.f('ix_corporate_clients_owner_cor_id'), 'corporate_clients', ['owner_cor_id'])
    op.create_index(op.f('ix_corporate_clients_status'), 'corporate_clients', ['status'])
    op.create_index(op.f('ix_corporate_clients_tax_id'), 'corporate_clients', ['tax_id'], unique=True)
    op.create_index(op.f('ix_corporate_clients_finance_company_id'), 'corporate_clients', ['finance_company_id'])
    op.create_index(op.f('ix_corporate_clients_created_at'), 'corporate_clients', ['created_at'])


def downgrade() -> None:
    """
    Удаление таблицы корпоративных клиентов
    """
    op.drop_index(op.f('ix_corporate_clients_created_at'), table_name='corporate_clients')
    op.drop_index(op.f('ix_corporate_clients_finance_company_id'), table_name='corporate_clients')
    op.drop_index(op.f('ix_corporate_clients_tax_id'), table_name='corporate_clients')
    op.drop_index(op.f('ix_corporate_clients_status'), table_name='corporate_clients')
    op.drop_index(op.f('ix_corporate_clients_owner_cor_id'), table_name='corporate_clients')
    op.drop_table('corporate_clients')
