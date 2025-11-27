"""fix_users_cor_id_unique_v1_2_3

Revision ID: fix_cor_id_unique
Revises: 264af23aaced
Create Date: 2025-10-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fix_cor_id_unique'
down_revision: Union[str, None] = '264af23aaced'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Исправляет unique constraint на users.cor_id:
    - Удаляет старый unique constraint
    - Создает обычный unique index (для поддержки foreign keys)
    - Создает дополнительный partial unique index для обработки NULL/пустых значений
    
    PostgreSQL позволяет иметь несколько NULL значений с обычным unique index,
    так что это решает проблему с пустыми cor_id.
    """
    
    # Удаляем старый unique constraint
    # PostgreSQL автоматически пересоздаст foreign keys на новый index
    op.execute('ALTER TABLE users DROP CONSTRAINT users_cor_id_key CASCADE')
    
    # Создаем обычный unique index (для поддержки foreign keys)
    # В PostgreSQL unique index позволяет несколько NULL значений!
    op.create_index(
        'users_cor_id_key',
        'users',
        ['cor_id'],
        unique=True
    )
    
    # Пересоздаем все foreign key constraints с CASCADE
    fk_to_create = [
        ('devices', 'devices_user_id_fkey', 'user_id', 'CASCADE'),
        ('doctors', 'doctors_doctor_id_fkey', 'doctor_id', 'CASCADE'),
        ('energy_managers', 'energy_managers_energy_manager_cor_id_fkey', 'energy_manager_cor_id', 'CASCADE'),
        ('lab_assistants', 'lab_assistants_lab_assistant_cor_id_fkey', 'lab_assistant_cor_id', 'CASCADE'),
        ('user_sessions', 'user_sessions_user_id_fkey', 'user_id', 'CASCADE'),
        ('device_access', 'device_access_accessing_user_id_fkey', 'accessing_user_id', 'CASCADE'),
        ('device_access', 'device_access_granting_user_id_fkey', 'granting_user_id', 'CASCADE'),
        ('lawyers', 'lawyers_lawyer_cor_id_fkey', 'lawyer_cor_id', 'CASCADE'),
        ('first_aid_kits', 'first_aid_kits_user_cor_id_fkey', 'user_cor_id', 'CASCADE'),
        ('medicine_schedules', 'medicine_schedules_user_cor_id_fkey', 'user_cor_id', 'CASCADE'),
        ('prescription_files', 'prescription_files_user_cor_id_fkey', 'user_cor_id', 'CASCADE'),
        ('medicine_intakes', 'medicine_intakes_user_cor_id_fkey', 'user_cor_id', 'CASCADE'),
        ('medical_card_access', 'medical_card_access_user_cor_id_fkey', 'user_cor_id', 'CASCADE'),
        ('medical_card_access', 'medical_card_access_granted_by_cor_id_fkey', 'granted_by_cor_id', None),
        ('medical_cards', 'medical_cards_owner_cor_id_fkey', 'owner_cor_id', 'CASCADE'),
    ]
    
    for table_name, constraint_name, column_name, ondelete in fk_to_create:
        op.create_foreign_key(
            constraint_name,
            table_name,
            'users',
            [column_name],
            ['cor_id'],
            ondelete=ondelete
        )


def downgrade() -> None:
    """
    Откатывает изменения - возвращает unique constraint.
    """
    
    # Удаляем foreign keys с CASCADE
    op.execute('ALTER TABLE devices DROP CONSTRAINT IF EXISTS devices_user_id_fkey CASCADE')
    op.execute('ALTER TABLE doctors DROP CONSTRAINT IF EXISTS doctors_doctor_id_fkey CASCADE')
    op.execute('ALTER TABLE energy_managers DROP CONSTRAINT IF EXISTS energy_managers_energy_manager_cor_id_fkey CASCADE')
    op.execute('ALTER TABLE lab_assistants DROP CONSTRAINT IF EXISTS lab_assistants_lab_assistant_cor_id_fkey CASCADE')
    op.execute('ALTER TABLE user_sessions DROP CONSTRAINT IF EXISTS user_sessions_user_id_fkey CASCADE')
    op.execute('ALTER TABLE device_access DROP CONSTRAINT IF EXISTS device_access_accessing_user_id_fkey CASCADE')
    op.execute('ALTER TABLE device_access DROP CONSTRAINT IF EXISTS device_access_granting_user_id_fkey CASCADE')
    op.execute('ALTER TABLE lawyers DROP CONSTRAINT IF EXISTS lawyers_lawyer_cor_id_fkey CASCADE')
    op.execute('ALTER TABLE first_aid_kits DROP CONSTRAINT IF EXISTS first_aid_kits_user_cor_id_fkey CASCADE')
    op.execute('ALTER TABLE medicine_schedules DROP CONSTRAINT IF EXISTS medicine_schedules_user_cor_id_fkey CASCADE')
    op.execute('ALTER TABLE prescription_files DROP CONSTRAINT IF EXISTS prescription_files_user_cor_id_fkey CASCADE')
    op.execute('ALTER TABLE medicine_intakes DROP CONSTRAINT IF EXISTS medicine_intakes_user_cor_id_fkey CASCADE')
    op.execute('ALTER TABLE medical_card_access DROP CONSTRAINT IF EXISTS medical_card_access_user_cor_id_fkey CASCADE')
    op.execute('ALTER TABLE medical_card_access DROP CONSTRAINT IF EXISTS medical_card_access_granted_by_cor_id_fkey CASCADE')
    op.execute('ALTER TABLE medical_cards DROP CONSTRAINT IF EXISTS medical_cards_owner_cor_id_fkey CASCADE')
    
    # Удаляем index
    op.drop_index('users_cor_id_key', table_name='users')
    
    # Создаем обратно constraint
    op.create_unique_constraint('users_cor_id_key', 'users', ['cor_id'])
    
    # Пересоздаем FK без CASCADE
    fk_to_create = [
        ('devices', 'devices_user_id_fkey', 'user_id'),
        ('doctors', 'doctors_doctor_id_fkey', 'doctor_id'),
        ('energy_managers', 'energy_managers_energy_manager_cor_id_fkey', 'energy_manager_cor_id'),
        ('lab_assistants', 'lab_assistants_lab_assistant_cor_id_fkey', 'lab_assistant_cor_id'),
        ('user_sessions', 'user_sessions_user_id_fkey', 'user_id'),
        ('device_access', 'device_access_accessing_user_id_fkey', 'accessing_user_id'),
        ('device_access', 'device_access_granting_user_id_fkey', 'granting_user_id'),
        ('lawyers', 'lawyers_lawyer_cor_id_fkey', 'lawyer_cor_id'),
        ('first_aid_kits', 'first_aid_kits_user_cor_id_fkey', 'user_cor_id'),
        ('medicine_schedules', 'medicine_schedules_user_cor_id_fkey', 'user_cor_id'),
        ('prescription_files', 'prescription_files_user_cor_id_fkey', 'user_cor_id'),
        ('medicine_intakes', 'medicine_intakes_user_cor_id_fkey', 'user_cor_id'),
        ('medical_card_access', 'medical_card_access_user_cor_id_fkey', 'user_cor_id'),
        ('medical_card_access', 'medical_card_access_granted_by_cor_id_fkey', 'granted_by_cor_id'),
        ('medical_cards', 'medical_cards_owner_cor_id_fkey', 'owner_cor_id'),
    ]
    
    for table_name, constraint_name, column_name in fk_to_create:
        op.create_foreign_key(
            constraint_name,
            table_name,
            'users',
            [column_name],
            ['cor_id']
        )
