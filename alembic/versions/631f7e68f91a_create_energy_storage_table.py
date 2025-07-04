"""create energy storage table

Revision ID: 631f7e68f91a
Revises: 38b64534968d
Create Date: 2025-07-04 13:14:19.318597

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '631f7e68f91a'
down_revision: Union[str, None] = '38b64534968d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
