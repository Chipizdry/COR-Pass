"""
Energy domain models - energetic objects monitoring, Cerbo measurements, schedules
"""

from sqlalchemy import Column, String, ForeignKey, DateTime, Integer, Float, Boolean, Time, Interval, Index, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
import uuid

from .base import Base
from .enums import AccessLevel


class EnergeticObject(Base):
    """
    Энергетический объект - объект для мониторинга энергопотребления и управления
    """
    __tablename__ = "energetic_objects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True, comment="Имя/название объекта")
    description = Column(String, nullable=True, comment="Описание объекта")
    protocol = Column(String, nullable=True, comment="Протокол связи")
    vendor = Column(String, nullable=True, comment="Производитель/вендор инвертора")
    ip_address = Column(String, nullable=True, comment="IP-адрес объекта")
    port = Column(Integer, nullable=True, comment="Порт объекта")
    inverter_login = Column(String, nullable=True, comment="Логин для доступа к инвертору")
    inverter_password = Column(String, nullable=True, comment="Пароль для доступа к инвертору")
    timezone = Column(
        String,
        nullable=True,
        default='Europe/Kiev',
        server_default='Europe/Kiev',
        comment="Часовой пояс объекта (например: Europe/Kiev)"
    )
    
    modbus_config_file = Column(
        String,
        nullable=True,
        comment="Имя файла конфигурации Modbus регистров (например: victron_cerbo_gx.json)"
    )

    telegram_chat_ids = Column(String, nullable=True)

    is_active = Column(Boolean, default=False, comment="Активен ли фоновый опрос")

    # Relationships
    measurements = relationship("CerboMeasurement", back_populates="energetic_object", cascade="all, delete-orphan")
    schedules = relationship("EnergeticSchedule", back_populates="energetic_object", cascade="all, delete-orphan")
    polling_tasks = relationship("DevicePollingTask", back_populates="energetic_object", cascade="all, delete-orphan")


class EnergeticDevice(Base):
    """
    Энергетическое устройство, подключаемое по WebSocket (modbus/Cerbo и т.д.)
    device_id соответствует session_id при подключении.
    """

    __tablename__ = "energetic_devices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=True)
    device_id = Column(String(255), unique=True, index=True, nullable=False)
    owner_cor_id = Column(String(250), ForeignKey("users.cor_id"), nullable=False, index=True)
    protocol = Column(String, nullable=True)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="energetic_devices", foreign_keys=[owner_cor_id])
    accesses = relationship("EnergeticDeviceAccess", back_populates="device", cascade="all, delete-orphan")


class EnergeticDeviceAccess(Base):
    """
    Доступ к энергетическому устройству (шаринг между пользователями)
    """

    __tablename__ = "energetic_device_access"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), ForeignKey("energetic_devices.id"), nullable=False)
    granting_user_cor_id = Column(String(36), ForeignKey("users.cor_id"), nullable=True)
    accessing_user_cor_id = Column(String(36), ForeignKey("users.cor_id"), nullable=False)
    access_level = Column(
        Enum(
            AccessLevel,
            values_callable=lambda x: [e.value for e in x],
            name="accesslevel",
        ),
        nullable=True,
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    device = relationship("EnergeticDevice", back_populates="accesses")
    granting_user = relationship("User", foreign_keys=[granting_user_cor_id], back_populates="energetic_granted_accesses")
    accessing_user = relationship("User", foreign_keys=[accessing_user_cor_id], back_populates="energetic_received_accesses")


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


class DevicePollingTask(Base):
    """
    Задача фонового опроса устройства - настройка периодического опроса энергетических объектов
    """
    __tablename__ = "device_polling_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    energetic_object_id = Column(String(36), ForeignKey("energetic_objects.id"), nullable=False, index=True)
    
    task_type = Column(
        String, 
        nullable=False, 
        comment="Тип задачи: cerbo_collection | schedule_check | modbus_registers | custom_command"
    )
    
    command_config = Column(
        JSONB,
        nullable=True,
        comment="Конфигурация команд в JSON формате (какие регистры читать, параметры команды)"
    )
    
    interval_seconds = Column(
        Float,
        nullable=False,
        default=5,
        comment="Интервал опроса в секундах"
    )
    
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Активна ли задача опроса"
    )
    
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    # Relationships
    energetic_object = relationship("EnergeticObject", back_populates="polling_tasks")
    
    def __repr__(self):
        return (
            f"<DevicePollingTask(id='{self.id}', object_id='{self.energetic_object_id}', "
            f"task_type='{self.task_type}', interval={self.interval_seconds}s, is_active={self.is_active})>"
        )


class WebSocketBroadcastTask(Base):
    """
    Задача фоновой рассылки команд через WebSocket на конкретное устройство
    """
    __tablename__ = "websocket_broadcast_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_name = Column(String, nullable=False, comment="Имя задачи")
    session_id = Column(String, nullable=False, index=True, comment="Session ID устройства")
    
    command_type = Column(
        String,
        nullable=False,
        comment="Тип команды: pi30 | modbus_read"
    )
    
    command_payload = Column(
        JSONB,
        nullable=False,
        comment="Полезная нагрузка команды (для pi30: {pi30: hex}, для modbus_read: {hex_data: ...})"
    )
    
    interval_seconds = Column(
        Float,
        nullable=False,
        default=5,
        comment="Интервал отправки команды в секундах"
    )
    
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Активна ли задача рассылки"
    )
    
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    created_by = Column(String, nullable=True, comment="Кто создал задачу (user_id или admin)")
    
    def __repr__(self):
        return (
            f"<WebSocketBroadcastTask(id='{self.id}', task_name='{self.task_name}', "
            f"session_id='{self.session_id}', command_type='{self.command_type}', "
            f"interval={self.interval_seconds}s, is_active={self.is_active})>"
        )
