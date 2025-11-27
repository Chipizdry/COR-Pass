"""
Roles domain models - lab assistants, energy managers, financiers
"""

from sqlalchemy import Column, String, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
import uuid

from .base import Base


class LabAssistant(Base):
    """
    Лаборант - сотрудник лаборатории с расширенными правами
    """
    __tablename__ = "lab_assistants"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lab_assistant_cor_id = Column(String(36), ForeignKey("users.cor_id"), unique=True, nullable=False)
    
    first_name = Column(String(100), nullable=True)
    surname = Column(String(100), nullable=True)
    middle_name = Column(String(100), nullable=True)
    lab_assistants_photo = Column(LargeBinary, nullable=True)

    # Relationships
    user = relationship("User", back_populates="user_lab_assistants")


class EnergyManager(Base):
    """
    Энергоменеджер - сотрудник для управления энергетическими объектами
    """
    __tablename__ = "energy_managers"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    energy_manager_cor_id = Column(String(36), ForeignKey("users.cor_id"), unique=True, nullable=False)
    
    first_name = Column(String(100), nullable=True)
    surname = Column(String(100), nullable=True)
    middle_name = Column(String(100), nullable=True)
    lab_assistants_photo = Column(LargeBinary, nullable=True)  # Note: legacy field name

    # Relationships
    user = relationship("User", back_populates="user_energy_managers")


class Financier(Base):
    """
    Финансист - сотрудник для управления финансовыми операциями
    """
    __tablename__ = "financiers"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    financier_cor_id = Column(String(36), ForeignKey("users.cor_id"), unique=True, nullable=False)
    
    first_name = Column(String(100), nullable=True)
    surname = Column(String(100), nullable=True)
    middle_name = Column(String(100), nullable=True)

    # Relationships
    user = relationship("User", back_populates="user_financiers")
