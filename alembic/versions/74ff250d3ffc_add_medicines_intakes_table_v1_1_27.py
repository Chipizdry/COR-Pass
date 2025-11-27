"""add medicines intakes table  v1.1.27

Revision ID: 74ff250d3ffc
Revises: 1f802a4585b7
Create Date: 2025-10-23 20:14:18.254230

"""
from typing import Sequence, Union
from datetime import datetime, timedelta

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '74ff250d3ffc'
down_revision: Union[str, None] = '1f802a4585b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def create_intake_records(schedules, connection):
    """Создает записи о приемах для существующих расписаний"""
    now = datetime.now()
    
    for schedule in schedules:
        # Проверяем наличие необходимых данных
        if not all([schedule.id, schedule.user_cor_id, schedule.start_date]):
            continue
            
        # Пропускаем симптоматические расписания
        if schedule.symptomatically:
            continue
            
        # Проверяем, не закончилось ли расписание
        end_date = schedule.start_date + timedelta(days=schedule.duration_days) if schedule.duration_days else None
        if end_date and end_date < now.date():
            continue

        # Получаем времена приема
        intake_times = []
        if schedule.intake_times:
            # Если intake_times это JSON массив
            if isinstance(schedule.intake_times, list):
                intake_times = schedule.intake_times
            # Если это строка с разделителями
            elif isinstance(schedule.intake_times, str):
                intake_times = [t.strip() for t in schedule.intake_times.split(',')]

        if not intake_times and schedule.times_per_day:
            # Если времена не заданы, но задана кратность - генерируем равномерно
            start_hour = 8  # Начинаем с 8 утра
            interval = 24 // schedule.times_per_day
            intake_times = [f"{(start_hour + i * interval):02d}:00" for i in range(schedule.times_per_day)]

        # Создаем записи на будущие приемы
        for day_offset in range((end_date - now.date()).days if end_date else 30):  # Если нет end_date, создаем на 30 дней
            target_date = now.date() + timedelta(days=day_offset)
            if target_date >= schedule.start_date:
                for time_str in intake_times:
                    try:
                        hours, minutes = map(int, time_str.split(":"))
                        planned_time = datetime.combine(target_date, datetime.min.time().replace(hour=hours, minute=minutes))
                        
                        if planned_time > now:  # Создаем только будущие приемы
                            connection.execute(
                            sa.text(
                                """
                                INSERT INTO medicine_intakes 
                                (id, schedule_id, user_cor_id, planned_datetime, status, created_at, updated_at)
                                VALUES 
                                (gen_random_uuid(), :schedule_id, :user_cor_id, :planned_datetime, :status, :created_at, :updated_at)
                                """
                            ),
                            {
                                "schedule_id": schedule.id,
                                "user_cor_id": schedule.user_cor_id,
                                "planned_datetime": planned_time,
                                "status": "PLANNED",
                                "created_at": now,
                                "updated_at": now
                            }
                        )
                    except (ValueError, TypeError) as e:
                        print(f"Error processing time {time_str} for schedule {schedule.id}: {e}")
                        continue

def upgrade() -> None:
    # Создаем таблицу medicine_intakes с использованием существующего enum типа
    op.create_table('medicine_intakes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('schedule_id', sa.String(length=36), nullable=False),
        sa.Column('user_cor_id', sa.String(length=36), nullable=False),
        sa.Column('planned_datetime', sa.DateTime(), nullable=False),
        sa.Column('actual_datetime', sa.DateTime(), nullable=True),
        sa.Column('status', 
                 sa.Enum('PLANNED', 'COMPLETED', 'SKIPPED', 'DELAYED', 
                        name='medicineintakestatus', 
                        create_type=False), 
                 nullable=False, 
                 server_default='PLANNED'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['schedule_id'], ['medicine_schedules.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_cor_id'], ['users.cor_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Создаем индексы для оптимизации запросов
    op.create_index('idx_medicine_intakes_user_cor_id', 'medicine_intakes', ['user_cor_id'])
    op.create_index('idx_medicine_intakes_schedule_id', 'medicine_intakes', ['schedule_id'])
    op.create_index('idx_medicine_intakes_planned_datetime', 'medicine_intakes', ['planned_datetime'])
    op.create_index('idx_medicine_intakes_status', 'medicine_intakes', ['status'])

    # Получаем существующие расписания и создаем записи
    connection = op.get_bind()
    result = connection.execute(
        sa.text(
            """
            SELECT id, user_cor_id, start_date, duration_days, times_per_day, 
                   intake_times, symptomatically
            FROM medicine_schedules
            WHERE symptomatically IS NULL OR symptomatically = FALSE
            """
        )
    )
    schedules = result.fetchall()
    
    # Создаем записи для существующих расписаний
    create_intake_records(schedules, connection)

    # Получаем существующие расписания и создаем записи
    connection = op.get_bind()
    schedules = connection.execute(
        sa.text(
            """
            SELECT id, user_cor_id, start_date, duration_days, times_per_day, 
                   intake_times, symptomatically
            FROM medicine_schedules
            WHERE symptomatically = FALSE
            """
        )
    ).fetchall()
    
    create_intake_records(schedules, connection)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index('idx_medicines_name', 'medicines', ['name'], unique=False)
    op.drop_table('medicine_intakes')
    op.execute("DROP TYPE medicineintakestatus")
    # ### end Alembic commands ###
