"""
Energy domain models - energetic objects monitoring, Cerbo measurements, schedules
"""

from sqlalchemy import Column, String, ForeignKey, DateTime, Integer, Float, Boolean, Time, Interval, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
import uuid

from .base import Base


class EnergeticObject(Base):
    """
    Энергетический объект - объект для мониторинга энергопотребления и управления
    """
    __tablename__ = "energetic_objects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True, comment="Имя/название объекта")
    description = Column(String, nullable=True, comment="Описание объекта")
    protocol = Column(String, nullable=True, comment="Протокол связи")
    ip_address = Column(String, nullable=True, comment="IP-адрес объекта")
    port = Column(Integer, nullable=True, comment="Порт объекта")
    inverter_login = Column(String, nullable=True, comment="Логин для доступа к инвертору")
    inverter_password = Column(String, nullable=True, comment="Пароль для доступа к инвертору")
    timezone = Column(
        String,
        nullable=False,
        default='Europe/Kiev',
        server_default='Europe/Kiev',
        comment="Часовой пояс объекта (например: Europe/Kiev)"
    )

    modbus_registers = Column(
        JSONB,
        nullable=True,
        comment="Карта регистров Modbus (динамическая структура в формате JSON)"
    )
    is_active = Column(Boolean, default=False, comment="Активен ли фоновый опрос")

    # Relationships
    measurements = relationship("CerboMeasurement", back_populates="energetic_object", cascade="all, delete-orphan")
    schedules = relationship("EnergeticSchedule", back_populates="energetic_object", cascade="all, delete-orphan")


class CerboMeasurement(Base):
    """
    Измерение Cerbo - данные с устройств мониторинга энергопотребления Cerbo GX
    """
    __tablename__ = "cerbo_measurements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    energetic_object_id = Column(String(36), ForeignKey("energetic_objects.id"), nullable=False, index=True)
    
    created_at = Column(DateTime, nullable=False, default=func.now())
    measured_at = Column(DateTime, nullable=False, comment="Дата и время измерения")

    object_name: Column[str] = Column(String, nullable=True, index=True)

    # Данные из battery_status
    general_battery_power: Column[float] = Column(Float, nullable=False)

    # Данные из inverter_power_status
    inverter_total_ac_output: Column[float] = Column(Float, nullable=False)

    # Данные из ess_ac_status
    ess_total_input_power: Column[float] = Column(Float, nullable=False)

    # Данные из solarchargers_status
    solar_total_pv_power: Column[float] = Column(Float, nullable=False)

    soc: Column[float] = Column(Float, nullable=True)

    # Relationships
    energetic_object = relationship("EnergeticObject", back_populates="measurements")

    def __repr__(self):
        return (
            f"<CerboMeasurement(id={self.id}, measured_at='{self.measured_at}', "
            f"object_name='{self.object_name}', general_battery_power={self.general_battery_power})>"
        )


class EnergeticSchedule(Base):
    """
    Расписание энергетических задач - управление режимами работы инвертора
    """
    __tablename__ = "energetic_schedule"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    energetic_object_id = Column(String(36), ForeignKey("energetic_objects.id"), nullable=False, index=True)

    # Параметры времени
    start_time = Column(Time, nullable=False, comment="Время начала работы режима (ЧЧ:ММ)")
    duration = Column(Interval, nullable=False, comment="Продолжительность режима")
    end_time = Column(Time, nullable=False, comment="Время окончания работы режима")

    # Параметры работы инвертора
    grid_feed_w = Column(Integer, nullable=False, comment="Отдача в сеть (Вт)")
    battery_level_percent = Column(Integer, nullable=False, comment="Целевой уровень батареи (%)")

    # Статусы расписания
    is_active = Column(Boolean, nullable=False, default=False)
    is_manual_mode = Column(Boolean, nullable=False, default=False)
    charge_battery_value = Column(Integer, nullable=False, default=300)

    # Relationships
    energetic_object = relationship("EnergeticObject", back_populates="schedules")

    def __repr__(self):
        return (
            f"<EnergeticSchedule(id='{self.id}', start_time={self.start_time}, "
            f"duration={self.duration}, end_time={self.end_time}, "
            f"grid_feed_w={self.grid_feed_w}, battery_level_percent={self.battery_level_percent}, "
            f"charge_battery_value={self.charge_battery_value}, is_active={self.is_active}, "
            f"is_manual_mode={self.is_manual_mode})>"
        )
