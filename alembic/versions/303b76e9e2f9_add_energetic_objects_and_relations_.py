"""add energetic_objects and relations + migrate existing data  v1.1.15

Revision ID: 303b76e9e2f9
Revises: a3294d709180
Create Date: 2025-09-22 11:58:51.346281

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision: str = '303b76e9e2f9'
down_revision: Union[str, None] = 'a3294d709180'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # --- создаем таблицу объектов ---
    op.create_table(
        "energetic_objects",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("modbus_registers", sa.dialects.postgresql.JSONB(), nullable=True),
    )

    op.add_column("cerbo_measurements", sa.Column("energetic_object_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_cerbo_measurements_energetic_object",
        "cerbo_measurements",
        "energetic_objects",
        ["energetic_object_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.add_column("energetic_schedule", sa.Column("energetic_object_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_energetic_schedule_energetic_object",
        "energetic_schedule",
        "energetic_objects",
        ["energetic_object_id"],
        ["id"],
        ondelete="CASCADE",
    )

    conn = op.get_bind()
    cor_azk_id = str(uuid.uuid4())
    conn.execute(
        sa.text(
            "INSERT INTO energetic_objects (id, name, description, modbus_registers) "
            "VALUES (:id, :name, :desc, :regs)"
        ),
        {"id": cor_azk_id, "name": "COR-AZK", "desc": "Основной энергетический объект", "regs": None},
    )

    conn.execute(
        sa.text("UPDATE cerbo_measurements SET energetic_object_id = :id"),
        {"id": cor_azk_id},
    )
    conn.execute(
        sa.text("UPDATE energetic_schedule SET energetic_object_id = :id"),
        {"id": cor_azk_id},
    )

    op.alter_column("cerbo_measurements", "energetic_object_id", nullable=False)
    op.alter_column("energetic_schedule", "energetic_object_id", nullable=False)


def downgrade():
    # убираем FK из schedules
    op.drop_constraint("fk_energetic_schedule_energetic_object", "energetic_schedule", type_="foreignkey")
    op.drop_column("energetic_schedule", "energetic_object_id")

    # убираем FK из measurements
    op.drop_constraint("fk_cerbo_measurements_energetic_object", "cerbo_measurements", type_="foreignkey")
    op.drop_column("cerbo_measurements", "energetic_object_id")

    # дропаем таблицу объектов
    op.drop_table("energetic_objects")
    # ### end Alembic commands ###
