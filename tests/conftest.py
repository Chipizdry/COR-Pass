"""Pytest configuration and fixtures for tests."""
import asyncio
import os
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import LargeBinary, Date

from cor_pass.config.config import settings
from cor_pass.database.models.base import Base
from cor_pass.database.models.user import User
from cor_pass.database.models.health import SibionicsAuth
from main import app


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_engine():
    """Create test database engine."""
    from sqlalchemy import MetaData, Table, Column, String, DateTime, Integer, Boolean, ForeignKey
    from sqlalchemy.sql import func
    
    # Create engine with SQLite compatibility
    engine = create_async_engine(
        TEST_DATABASE_URL, 
        echo=False,
        connect_args={"check_same_thread": False}
    )
    
    # Create only specific tables we need for testing
    metadata = MetaData()
    
    # Create full User table matching the real model
    users_table = Table(
        'users', metadata,
        Column('id', String(36), primary_key=True),
        Column('cor_id', String(250), nullable=True),
        Column('email', String(250), nullable=False, unique=True),
        Column('backup_email', String(250), nullable=True),
        Column('password', String(250), nullable=False),
        Column('last_password_change', DateTime, server_default=func.now()),
        Column('access_token', String(500), nullable=True),
        Column('refresh_token', String(500), nullable=True),
        Column('recovery_code', String, nullable=True),  # LargeBinary -> String for SQLite
        Column('is_active', Boolean, default=True),
        Column('status', String(20), default='basic'),  # Enum -> String for SQLite
        Column('unique_cipher_key', String(250), nullable=False),
        Column('user_sex', String(10), nullable=True),
        Column('birth', Integer, nullable=True),
        Column('user_index', Integer, nullable=True),
        Column('created_at', DateTime, server_default=func.now()),
    )

    # Create minimal SibionicsAuth table for tests
    sibionics_auth_table = Table(
        'sibionics_auth', metadata,
        Column('id', String(36), primary_key=True),  # UUID string
        Column('user_id', String(36), nullable=False),
        Column('biz_id', String(255), nullable=True),
        Column('access_token', String(500), nullable=True),  # Nullable!
        Column('expires_in', DateTime, nullable=True),  # Nullable!
        Column('is_active', Boolean, default=True),
        Column('created_at', DateTime, nullable=True),  # Nullable for SQLite
        Column('updated_at', DateTime, nullable=True),  # Nullable for SQLite
    )

    # Create BloodPressureMeasurement table for tests
    blood_pressure_table = Table(
        'blood_pressure_measurements', metadata,
        Column('id', String(36), primary_key=True),
        Column('user_id', String(36), ForeignKey('users.id'), nullable=False, index=True),
        Column('systolic_pressure', Integer, nullable=False),
        Column('diastolic_pressure', Integer, nullable=False),
        Column('pulse', Integer, nullable=False),
        Column('measured_at', DateTime, nullable=False),
        Column('created_at', DateTime, nullable=False, server_default=func.now()),
    )

    # Create UserSettings table for tests
    user_settings_table = Table(
        'user_settings', metadata,
        Column('user_id', String(36), ForeignKey('users.id'), primary_key=True),
        Column('local_password_storage', Boolean, default=False),
        Column('cloud_password_storage', Boolean, default=True),
        Column('local_medical_storage', Boolean, default=False),
        Column('cloud_medical_storage', Boolean, default=True),
    )

    # Create MedicalCards table for tests
    medical_cards_table = Table(
        'medical_cards', metadata,
        Column('id', String(36), primary_key=True),
        Column('owner_cor_id', String(36), ForeignKey('users.cor_id', ondelete='CASCADE'), nullable=False, unique=True),
        Column('card_color', String(20), nullable=True, default='#4169E1'),
        Column('display_name', String(100), nullable=True),
        Column('is_active', Boolean, default=True),
        Column('created_at', DateTime, nullable=False, server_default=func.now()),
        Column('updated_at', DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
    )

    # Create Lawyers table for tests (required for role checking during signup)
    lawyers_table = Table(
        'lawyers', metadata,
        Column('id', String(36), primary_key=True),
        Column('lawyer_cor_id', String(36), ForeignKey('users.cor_id'), unique=True, nullable=False),
        Column('first_name', String(100), nullable=True),
        Column('surname', String(100), nullable=True),
        Column('middle_name', String(100), nullable=True),
    )

    # Create Doctors table for tests (required for role checking during signup)
    doctors_table = Table(
        'doctors', metadata,
        Column('id', String(36), primary_key=True),
        Column('doctor_id', String(36), ForeignKey('users.cor_id'), unique=True, nullable=False),
        Column('work_email', String(250), unique=True, nullable=False),
        Column('phone_number', String(20), nullable=True),
        Column('first_name', String(100), nullable=True),
        Column('middle_name', String(100), nullable=True),
        Column('last_name', String(100), nullable=True),
        Column('doctors_photo', LargeBinary, nullable=True),
        Column('scientific_degree', String(100), nullable=True),
        Column('date_of_last_attestation', Date, nullable=True),
        Column('status', String(50), nullable=True),
        Column('passport_code', String(20), nullable=True),
        Column('taxpayer_identification_number', String(20), nullable=True),
        Column('reserv_scan_data', LargeBinary, nullable=True),
        Column('reserv_scan_file_type', String, nullable=True),
        Column('date_of_next_review', Date, nullable=True),
        Column('place_of_registration', String, nullable=True),
    )

    # Create LabAssistants table for tests (required for role checking during signup)
    lab_assistants_table = Table(
        'lab_assistants', metadata,
        Column('id', String(36), primary_key=True),
        Column('lab_assistant_cor_id', String(36), ForeignKey('users.cor_id'), unique=True, nullable=False),
        Column('first_name', String(100), nullable=True),
        Column('surname', String(100), nullable=True),
        Column('middle_name', String(100), nullable=True),
        Column('lab_assistants_photo', LargeBinary, nullable=True),
    )

    # Create EnergyManagers table for tests (required for role checking during signup)
    energy_managers_table = Table(
        'energy_managers', metadata,
        Column('id', String(36), primary_key=True),
        Column('energy_manager_cor_id', String(36), ForeignKey('users.cor_id'), unique=True, nullable=False),
        Column('first_name', String(100), nullable=True),
        Column('surname', String(100), nullable=True),
        Column('middle_name', String(100), nullable=True),
        Column('lab_assistants_photo', LargeBinary, nullable=True),
    )

    # Create Financiers table for tests (required for role checking during signup)
    financiers_table = Table(
        'financiers', metadata,
        Column('id', String(36), primary_key=True),
        Column('financier_cor_id', String(36), ForeignKey('users.cor_id'), unique=True, nullable=False),
        Column('first_name', String(100), nullable=True),
        Column('surname', String(100), nullable=True),
        Column('middle_name', String(100), nullable=True),
    )

    # Create UserSession table for tests (required for signup/login flows)
    user_sessions_table = Table(
        'user_sessions', metadata,
        Column('id', String(36), primary_key=True),
        Column('user_id', String(36), ForeignKey('users.cor_id'), nullable=False, index=True),
        Column('device_type', String(250), nullable=True),
        Column('device_info', String(250), nullable=True),
        Column('app_id', String(250), nullable=True),
        Column('device_id', String(250), nullable=True),
        Column('ip_address', String(250), nullable=True),
        Column('device_os', String(250), nullable=True),
        Column('jti', String, nullable=True, unique=True),
        Column('refresh_token', LargeBinary, nullable=True),
        Column('access_token', LargeBinary, nullable=True),
        Column('created_at', DateTime, nullable=False, server_default=func.now()),
        Column('updated_at', DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    
    yield engine
    
    # Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
    
    await engine.dispose()
@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""
    async def override_get_db():
        yield db_session
    
    from cor_pass.database.db import get_db
    from cor_pass.config.config import settings
    from fastapi_limiter import FastAPILimiter
    from fastapi_limiter.depends import RateLimiter
    from unittest.mock import AsyncMock
    import uuid
    
    # Completely bypass rate limiting by replacing RateLimiter instances with a no-op
    # We'll patch it on the module level before the app loads
    from fastapi_limiter.depends import RateLimiter
    import inspect
    
    # Store original for restoration
    original_init = RateLimiter.__init__
    original_call = RateLimiter.__call__
    
    # Create a no-op RateLimiter
    def noop_init(self, *args, **kwargs):
        pass  # Don't store anything
    
    async def noop_call(self):  # Dependency signature - just self
        return None  # Dependencies can return None
    
    RateLimiter.__init__ = noop_init
    RateLimiter.__call__ = noop_call
    
    # Mock Redis for FastAPILimiter (still needed for init)
    mock_redis = AsyncMock()
    async def unique_identifier(request):
        return f"test-{uuid.uuid4()}"
    
    await FastAPILimiter.init(mock_redis, identifier=unique_identifier)
    
    # Override redis_client globally for all modules that use it
    from cor_pass.database import redis_db
    from cor_pass.repository.user import cor_id
    from cor_pass.routes.user import auth
    
    mock_redis_client = AsyncMock()
    mock_redis_client.get = AsyncMock(return_value=None)  # No IP blocks in tests
    mock_redis_client.incr = AsyncMock(return_value=1)  # Always first attempt
    mock_redis_client.expire = AsyncMock(return_value=None)
    mock_redis_client.set = AsyncMock(return_value=None)
    mock_redis_client.delete = AsyncMock(return_value=None)
    mock_redis_client.exists = AsyncMock(return_value=False)  # For cor_id.py
    
    # Patch redis_client in all modules that import it
    redis_db.redis_client = mock_redis_client
    cor_id.redis_client = mock_redis_client  # Used in signup cor_id generation
    auth.redis_client = mock_redis_client  # Used in login IP blocking
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Add 'testserver' to allowed_hosts for testing
    original_allowed_hosts = settings.allowed_hosts.copy() if settings.allowed_hosts else []
    if settings.allowed_hosts is not None:
        settings.allowed_hosts.append("testserver")
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver"  # Use 'testserver' instead of 'test'
    ) as ac:
        yield ac
    
    # Restore original allowed_hosts
    settings.allowed_hosts = original_allowed_hosts
    app.dependency_overrides.clear()
    await FastAPILimiter.close()
    
    # Restore original RateLimiter
    RateLimiter.__init__ = original_init
    RateLimiter.__call__ = original_call


@pytest.fixture(scope="function")
async def authorized_client(db_session: AsyncSession, test_user: User) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with auth and access dependencies overridden."""
    async def override_get_db():
        yield db_session

    # Override current user dependency to return our test user
    from cor_pass.database.db import get_db
    from cor_pass.services.user.auth import auth_service
    from cor_pass.services.shared.access import user_access, doctor_access

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[auth_service.get_current_user] = lambda: test_user
    # Bypass access checks
    app.dependency_overrides[user_access] = lambda: test_user
    app.dependency_overrides[doctor_access] = lambda: test_user

    # Add 'testserver' to allowed_hosts for testing
    original_allowed_hosts = settings.allowed_hosts.copy() if settings.allowed_hosts else []
    if settings.allowed_hosts is not None:
        settings.allowed_hosts.append("testserver")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver"
    ) as ac:
        yield ac

    # Restore
    settings.allowed_hosts = original_allowed_hosts
    app.dependency_overrides.clear()


@pytest.fixture
def test_user_id() -> str:
    """Generate test user UUID."""
    return str(uuid4())


@pytest.fixture
async def test_user(db_session: AsyncSession, test_user_id: str) -> User:
    """Create test user in database."""
    user = User(
        id=test_user_id,
        email=f"test_{test_user_id[:8]}@example.com",
        password="fake_hashed_password_12345",
        unique_cipher_key="test_cipher_key_12345",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_sibionics_auth(
    db_session: AsyncSession,
    test_user: User
) -> SibionicsAuth:
    """Create test Sibionics authorization."""
    from datetime import datetime, timezone
    
    auth = SibionicsAuth(
        user_id=test_user.id,
        access_token="test_access_token_12345",
        expires_in=None,  # DateTime, not int
        is_active=True,
        biz_id=None,  # Will be set by callback
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(auth)
    await db_session.commit()
    await db_session.refresh(auth)
    return auth


@pytest.fixture
def sibionics_webhook_payload():
    """Create valid Sibionics webhook type 201 payload."""
    def _create_payload(
        user_id: str,
        biz_ids: list[str] = None,
        is_authorized: bool = True
    ):
        if biz_ids is None:
            biz_ids = ["test_biz_id_12345"]
        
        return {
            "type": 201,
            "content": {
                "bizIds": biz_ids,
                "thirdBizId": user_id,
                "isAuthorized": is_authorized,
                "grantTime": 1704067200000  # 2024-01-01 00:00:00
            }
        }
    return _create_payload


@pytest.fixture
def sibionics_webhook_headers():
    """Create valid Sibionics webhook headers with signature."""
    def _create_headers(body: str, sign_secret: str = "1234567812345678"):
        import hashlib
        
        app_id = "2lwUcVCY1PLbMKxf"
        nonce = "test_nonce_12345"
        
        # Calculate signature: MD5(appId + nonce + body + sign_secret).upper()
        sign_string = f"{app_id}{nonce}{body}{sign_secret}"
        signature = hashlib.md5(sign_string.encode()).hexdigest().upper()
        
        return {
            "appId": app_id,
            "nonce": nonce,
            "signature-app": signature,
            "Content-Type": "application/json"
        }
    return _create_headers
