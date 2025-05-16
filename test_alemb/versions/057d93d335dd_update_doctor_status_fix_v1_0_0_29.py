"""update doctor status fix  v1.0.0.29

Revision ID: 057d93d335dd
Revises: 9f3d8b1e055d
Create Date: 2025-05-12 12:52:11.660435

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '057d93d335dd'
down_revision: Union[str, None] = '9f3d8b1e055d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Предполагаем, что старые статусы могли быть 'pending', 'accepted', 'rejected'
    # и вы хотите привести их к новым значениям в нижнем регистре
    op.execute("UPDATE doctors SET status = 'pending' WHERE status = 'pending'")
    op.execute("UPDATE doctors SET status = 'approved' WHERE status = 'approved'")
    op.execute("UPDATE doctors SET status = 'rejected' WHERE status = 'rejected'")
    # Добавьте обновления для других возможных старых значений
    pass

def downgrade():
    # Обратное преобразование (если необходимо)
    op.execute("UPDATE doctors SET status = 'pending' WHERE status = 'pending'")
    op.execute("UPDATE doctors SET status = 'approved' WHERE status = 'approved'")
    op.execute("UPDATE doctors SET status = 'rejected' WHERE status = 'rejected'")
    pass
