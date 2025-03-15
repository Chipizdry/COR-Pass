"""refresh token to bytes

Revision ID: 8ad8a66e89d1
Revises: 77be80ad184f
Create Date: 2025-03-07 15:07:46.719475

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8ad8a66e89d1"
down_revision: Union[str, None] = "77be80ad184f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Изменяем тип столбца refresh_token на BYTEA с явным указанием преобразования
    op.alter_column(
        "user_sessions",
        "refresh_token",
        type_=sa.LargeBinary,
        postgresql_using="refresh_token::bytea",
        nullable=True,
    )


def downgrade():
    # Возвращаем тип столбца refresh_token обратно к TEXT (или другому исходному типу)
    op.alter_column(
        "user_sessions",
        "refresh_token",
        type_=sa.Text,
        postgresql_using="refresh_token::text",
        nullable=True,
    )
