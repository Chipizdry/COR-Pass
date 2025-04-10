"""Added UserSession columns

Revision ID: 4a44dbd4c364
Revises: 9ab539bdaedb
Create Date: 2025-03-07 12:19:59.513900

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4a44dbd4c364"
down_revision: Union[str, None] = "9ab539bdaedb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "user_sessions", sa.Column("device_type", sa.String(length=250), nullable=True)
    )
    op.add_column(
        "user_sessions", sa.Column("ip_adress", sa.String(length=250), nullable=True)
    )
    op.add_column(
        "user_sessions", sa.Column("device_os", sa.String(length=250), nullable=True)
    )
    op.create_unique_constraint(None, "users", ["backup_email"])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "users", type_="unique")
    op.drop_column("user_sessions", "device_os")
    op.drop_column("user_sessions", "ip_adress")
    op.drop_column("user_sessions", "device_type")
    # ### end Alembic commands ###
