"""add user sex, age and index nullable True

Revision ID: 8dd0a16a23f4
Revises: 977efb343b96
Create Date: 2024-12-30 10:32:54.085945

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8dd0a16a23f4"
down_revision: Union[str, None] = "977efb343b96"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
