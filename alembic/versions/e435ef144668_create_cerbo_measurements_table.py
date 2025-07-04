"""create cerbo_measurements table

Revision ID: e435ef144668
Revises: 38b64534968d
Create Date: 2025-07-04 12:34:45.345749

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e435ef144668'
down_revision: Union[str, None] = '38b64534968d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
