"""update doctor status test  v1.0.0.27

Revision ID: 02a8cefd38d4
Revises: a848fb5056c6
Create Date: 2025-05-12 12:33:03.595542

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import enum  
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '02a8cefd38d4'
down_revision: Union[str, None] = 'a848fb5056c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



# Импортируйте определение вашей Enum-класса
from cor_pass.database.models import Doctor_Status  # Замените your_app.models на фактический путь

old_values = [e.value for e in list(Doctor_Status)]
new_values = [e.value for e in list(Doctor_Status)]

old_doctor_status = postgresql.ENUM(*old_values, name='doctor_status')
new_doctor_status = postgresql.ENUM(*new_values, name='doctor_status')

def upgrade():
    op.execute("CREATE TYPE doctor_status AS ENUM ('" + "', '".join(new_values) + "')")
    op.drop_column('doctors', 'status')
    op.add_column('doctors', sa.Column('status', new_doctor_status, nullable=False, server_default='pending'))

def downgrade():
    op.drop_column('doctors', 'status')
    op.add_column('doctors', sa.Column('status', old_doctor_status, nullable=False, server_default='pending'))
    op.execute("DROP TYPE doctor_status")
