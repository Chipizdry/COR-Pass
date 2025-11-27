"""add_medical_cards_v1_2_1

Revision ID: 420532abcd12
Revises: 410342eed959
Create Date: 2025-01-29 10:00:00.000000

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = '420532abcd12'
down_revision: Union[str, None] = '410342eed959'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    
    result = conn.execute(text(
        "SELECT 1 FROM pg_type WHERE typname = 'medicalcardaccesslevel'"
    ))
    if not result.fetchone():
        conn.execute(text(
            "CREATE TYPE medicalcardaccesslevel AS ENUM ('view', 'edit', 'share')"
        ))
    
    result = conn.execute(text(
        "SELECT 1 FROM pg_type WHERE typname = 'medicalcardpurpose'"
    ))
    if not result.fetchone():
        conn.execute(text(
            "CREATE TYPE medicalcardpurpose AS ENUM ('relative', 'doctor', 'other')"
        ))
    
    medical_card_access_level = postgresql.ENUM('view', 'edit', 'share', name='medicalcardaccesslevel', create_type=False)
    medical_card_purpose = postgresql.ENUM('relative', 'doctor', 'other', name='medicalcardpurpose', create_type=False)
    
    op.create_table(
        'medical_cards',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('owner_cor_id', sa.String(length=36), nullable=False),
        sa.Column('card_color', sa.String(length=20), nullable=True, server_default='#4169E1'),
        sa.Column('display_name', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['owner_cor_id'], ['users.cor_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('owner_cor_id')
    )
    op.create_index('idx_medical_card_owner', 'medical_cards', ['owner_cor_id'], unique=False)
    
    op.create_table(
        'medical_card_access',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('medical_card_id', sa.String(length=36), nullable=False),
        sa.Column('user_cor_id', sa.String(length=36), nullable=False),
        sa.Column('access_level', medical_card_access_level, nullable=False, server_default='view'),
        sa.Column('purpose', medical_card_purpose, nullable=True),
        sa.Column('purpose_note', sa.String(length=255), nullable=True),
        sa.Column('granted_by_cor_id', sa.String(length=36), nullable=True),
        sa.Column('granted_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_accepted', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['medical_card_id'], ['medical_cards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_cor_id'], ['users.cor_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['granted_by_cor_id'], ['users.cor_id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('medical_card_id', 'user_cor_id', name='uq_card_user_access')
    )
    op.create_index('idx_medical_card_access_user', 'medical_card_access', ['user_cor_id'], unique=False)
    op.create_index('idx_medical_card_access_card', 'medical_card_access', ['medical_card_id'], unique=False)
    
    # Создание медицинских карт для всех существующих пользователей
    connection = op.get_bind()
    
    users = connection.execute(text("SELECT cor_id FROM users WHERE cor_id IS NOT NULL")).fetchall()
    
    for user in users:
        cor_id = user[0]
        card_id = str(uuid.uuid4())
        
        connection.execute(
            text("""
                INSERT INTO medical_cards (id, owner_cor_id, card_color, is_active, created_at, updated_at)
                VALUES (:id, :owner_cor_id, '#4169E1', true, NOW(), NOW())
            """),
            {"id": card_id, "owner_cor_id": cor_id}
        )
    
    print(f"Created medical cards for {len(users)} existing users")


def downgrade() -> None:

    op.drop_index('idx_medical_card_access_card', table_name='medical_card_access')
    op.drop_index('idx_medical_card_access_user', table_name='medical_card_access')
    op.drop_table('medical_card_access')
    
    op.drop_index('idx_medical_card_owner', table_name='medical_cards')
    op.drop_table('medical_cards')
    

    medical_card_purpose = postgresql.ENUM('relative', 'doctor', 'other', name='medicalcardpurpose')
    medical_card_purpose.drop(op.get_bind(), checkfirst=True)
    
    medical_card_access_level = postgresql.ENUM('view', 'edit', 'share', name='medicalcardaccesslevel')
    medical_card_access_level.drop(op.get_bind(), checkfirst=True)
