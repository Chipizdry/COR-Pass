"""Empty migration

Revision ID: f10027ac8cd0
Revises: 8dd0a16a23f4
Create Date: 2025-03-06 13:23:32.499950

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f10027ac8cd0"
down_revision: Union[str, None] = "8dd0a16a23f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
