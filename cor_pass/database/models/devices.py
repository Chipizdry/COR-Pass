"""
Devices domain models - device manufacturing, user devices, device sharing, printing devices
"""

from sqlalchemy import Column, String, ForeignKey, DateTime, Enum, Integer
from sqlalchemy.orm import relationship
import datetime
import uuid

from .base import Base
from .enums import DeviceStatus, AccessLevel


class ManufacturedDevice(Base):
    """
    Произведенное устройство - устройства на производстве
    """
    __tablename__ = 'manufactured_devices'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token = Column(String(255), unique=True, nullable=True)  # Токен устройства при производстве
    serial_number = Column(String(255), unique=True, nullable=True)
    status = Column(Enum(DeviceStatus), nullable=True, default=DeviceStatus.MANUFACTURED)

    # Relationships
    devices = relationship("Device", back_populates="manufactured_device")


class Device(Base):
    """
    Устройство пользователя - связь между пользователем и произведенным устройством
    """
    __tablename__ = 'devices'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token = Column(String(500), unique=True, nullable=True)  # JWT токен устройства
    name = Column(String(255), nullable=True)
    create_date = Column(DateTime, default=datetime.datetime.utcnow)

    # Foreign Keys
    user_id = Column(String(36), ForeignKey('users.cor_id'), nullable=True)
    serial_number = Column(String(255), ForeignKey('manufactured_devices.serial_number'), nullable=True)

    # Relationships
    user = relationship("User", back_populates="devices")
    manufactured_device = relationship("ManufacturedDevice", back_populates="devices")
    device_accesses = relationship("DeviceAccess", foreign_keys="DeviceAccess.device_id", back_populates="device")


class DeviceAccess(Base):
    """
    Доступ к устройству - управление совместным доступом к устройствам
    """
    __tablename__ = "device_access"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign Keys
    device_id = Column(String(36), ForeignKey('devices.id'), nullable=True)
    granting_user_id = Column(String(36), ForeignKey('users.cor_id'), nullable=True)
    accessing_user_id = Column(String(36), ForeignKey('users.cor_id'), nullable=True)

    access_level = Column(Enum(AccessLevel), nullable=True)
    create_date = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships (используем foreign_keys для разрешения ambiguous ForeignKey)
    device = relationship("Device", foreign_keys=[device_id], back_populates="device_accesses")
    granting_user = relationship("User", foreign_keys=[granting_user_id], back_populates="granted_accesses")
    accessing_user = relationship("User", foreign_keys=[accessing_user_id], back_populates="received_accesses")


class PrintingDevice(Base):
    """
    Печатающее устройство - конфигурация принтеров
    """
    __tablename__ = "printing_device"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_class = Column(String(255), nullable=False)
    device_identifier = Column(String(255), unique=True, nullable=False)
    subnet_mask = Column(String(255))
    gateway = Column(String(255))
    ip_address = Column(String(255), nullable=False)
    port = Column(Integer, nullable=True)
    comment = Column(String(500))
    location = Column(String(500))
