"""set is_favorite to False

Revision ID: 5c9accbc0516
Revises: 2ad78f6b3c51
Create Date: 2024-11-05 13:50:24.329262

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5c9accbc0516"
down_revision: Union[str, None] = "2ad78f6b3c51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE records SET is_favorite = FALSE")


def downgrade() -> None:
    pass
