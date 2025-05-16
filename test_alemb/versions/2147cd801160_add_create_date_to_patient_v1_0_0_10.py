"""add create date to patient v1.0.0.10

Revision ID: 2147cd801160
Revises: 7849fbaaefd2
Create Date: 2025-04-23 12:35:14.436762

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2147cd801160"
down_revision: Union[str, None] = "7849fbaaefd2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
