"""Refactor Patient model: add user_id FK, make patient_cor_id independent v1.1.0

Revision ID: 91f3353a1fd6
Revises: a6570481e591
Create Date: 2025-07-09 10:58:00.534348

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "91f3353a1fd6"
down_revision: Union[str, None] = "a6570481e591"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Commands manually adjusted for specific requirements ###

    # 1. удаляем СТАРЫЙ внешний ключ.
    op.drop_constraint("patients_patient_cor_id_fkey", "patients", type_="foreignkey")

    # 2. Добавляем новый столбец `user_id`.
    op.add_column("patients", sa.Column("user_id", sa.String(length=36), nullable=True))

    # 3. Обновляем существующие данные в `patients.user_id` и `patients.patient_cor_id`.
    op.execute(
        sa.text(
            """
            UPDATE patients AS p
            SET 
                user_id = u.id,                     
                patient_cor_id = u.cor_id           
            FROM users AS u
            WHERE p.patient_cor_id = u.cor_id;     
        """
        )
    )

    # 4. Изменяем тип и nullable статус `patient_cor_id`.
    op.alter_column(
        "patients",
        "patient_cor_id",
        existing_type=sa.VARCHAR(length=36),
        type_=sa.String(length=250),
        nullable=False,
        existing_nullable=False,
    )

    # 5. Создаем УНИКАЛЬНОЕ ограничение для `patients.patient_cor_id`.
    op.create_unique_constraint(
        op.f("uq_patients_patient_cor_id"), "patients", ["patient_cor_id"]
    )

    # 6. Создаем НОВЫЙ внешний ключ от `patients.user_id` к `users.id`.
    op.create_foreign_key(
        op.f("fk_patients_user_id_users_id"), "patients", "users", ["user_id"], ["id"]
    )
    op.create_unique_constraint(op.f("uq_patients_user_id"), "patients", ["user_id"])

    # ### End manually adjusted commands ###


def downgrade() -> None:
    # ### Commands manually adjusted for specific requirements ###

    # 1. Сначала удаляем НОВЫЙ внешний ключ и уникальное ограничение с `user_id`.
    op.drop_constraint(
        op.f("uq_patients_user_id"), "patients", type_="unique"
    )  # Удаляем unique constraint на user_id
    op.drop_constraint(
        op.f("fk_patients_user_id_users_id"), "patients", type_="foreignkey"
    )

    # 2. Удаляем столбец `user_id`.
    op.drop_column("patients", "user_id")

    # 3. Удаляем УНИКАЛЬНОЕ ограничение с `patient_cor_id`.
    op.drop_constraint(op.f("uq_patients_patient_cor_id"), "patients", type_="unique")

    # 4. Возвращаем тип `patient_cor_id` и nullable обратно, если это необходимо.
    op.alter_column(
        "patients",
        "patient_cor_id",
        existing_type=sa.String(length=250),
        type_=sa.VARCHAR(length=36),
        nullable=False,
        existing_nullable=False,
    )

    # 5. Восстанавливаем СТАРЫЙ внешний ключ.
    op.create_foreign_key(
        "patients_patient_cor_id_fkey",
        "patients",
        "users",
        ["patient_cor_id"],
        ["cor_id"],
    )

    # ### End manually adjusted commands ###
