"""change token size

Revision ID: 7062e2477f80
Revises: 5c9accbc0516
Create Date: 2024-12-10 11:38:11.733596

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7062e2477f80'
down_revision: Union[str, None] = '5c9accbc0516'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
