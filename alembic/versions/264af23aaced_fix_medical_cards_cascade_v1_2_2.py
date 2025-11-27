"""fix_medical_cards_cascade_v1_2_2

Revision ID: 264af23aaced
Revises: 420532abcd12
Create Date: 2025-10-31 11:44:04.227152

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '264af23aaced'
down_revision: Union[str, None] = '420532abcd12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Исправляет внешний ключ medical_cards.owner_cor_id 
    для корректного каскадного удаления при удалении пользователя.
    """
    # Удаляем старый constraint
    op.drop_constraint(
        'medical_cards_owner_cor_id_fkey', 
        'medical_cards', 
        type_='foreignkey'
    )
    
    # Создаем новый constraint с CASCADE
    op.create_foreign_key(
        'medical_cards_owner_cor_id_fkey',
        'medical_cards', 
        'users',
        ['owner_cor_id'], 
        ['cor_id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    """
    Откатывает изменения - возвращает constraint без CASCADE.
    """
    # Удаляем constraint с CASCADE
    op.drop_constraint(
        'medical_cards_owner_cor_id_fkey', 
        'medical_cards', 
        type_='foreignkey'
    )
    
    # Создаем старый constraint без CASCADE
    op.create_foreign_key(
        'medical_cards_owner_cor_id_fkey',
        'medical_cards', 
        'users',
        ['owner_cor_id'], 
        ['cor_id']
    )
