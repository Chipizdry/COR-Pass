"""Tests for user authentication endpoints (signup, login)."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.database.models.user import User


@pytest.mark.asyncio
class TestSignup:
    """Test user registration endpoint /auth/signup."""

    async def test_signup_success_minimal(self, client: AsyncClient):
        """Test successful signup with minimal required fields (email + password)."""
        payload = {
            "email": "newuser@example.com",
            "password": "SecurePass123",
        }

        resp = await client.post("/api/auth/signup", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # Check response structure
        assert "user" in data
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert "device_id" in data
        assert data["detail"] == "User successfully created"

        # Check user data
        user = data["user"]
        assert user["email"] == "newuser@example.com"
        assert user["is_active"] is True
        assert "id" in user
        assert "cor_id" in user  # COR-ID должен быть сгенерирован автоматически
        assert user["birth"] is None  # Не передавали
        assert user["user_sex"] is None  # Не передавали

    async def test_signup_with_birth_year(self, client: AsyncClient):
        """Test signup with birth year (год рождения)."""
        payload = {
            "email": "user_with_birth@example.com",
            "password": "SecurePass123",
            "birth": 1990,  # Год рождения
        }

        resp = await client.post("/api/auth/signup", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["user"]["birth"] == 1990

    async def test_signup_with_user_sex_male(self, client: AsyncClient):
        """Test signup with user_sex = 'M' (мужской)."""
        payload = {
            "email": "male_user@example.com",
            "password": "SecurePass123",
            "user_sex": "M",
        }

        resp = await client.post("/api/auth/signup", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["user"]["user_sex"] == "M"

    async def test_signup_with_user_sex_female(self, client: AsyncClient):
        """Test signup with user_sex = 'F' (женский)."""
        payload = {
            "email": "female_user@example.com",
            "password": "SecurePass123",
            "user_sex": "F",
        }

        resp = await client.post("/api/auth/signup", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["user"]["user_sex"] == "F"

    async def test_signup_with_user_sex_other(self, client: AsyncClient):
        """Test signup with user_sex = '*' (другое/не указано)."""
        payload = {
            "email": "other_user@example.com",
            "password": "SecurePass123",
            "user_sex": "*",
        }

        resp = await client.post("/api/auth/signup", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["user"]["user_sex"] == "*"

    async def test_signup_invalid_user_sex(self, client: AsyncClient):
        """Test signup with invalid user_sex value."""
        payload = {
            "email": "invalid_sex@example.com",
            "password": "SecurePass123",
            "user_sex": "X",  # Недопустимое значение
        }

        resp = await client.post("/api/auth/signup", json=payload)
        assert resp.status_code == 422
        error = resp.json()
        assert "detail" in error
        # Проверяем, что ошибка валидации упоминает правильные значения
        error_text = str(error)
        assert "M" in error_text or "F" in error_text or "user_sex" in error_text.lower()

    async def test_signup_birth_future_year(self, client: AsyncClient):
        """Test signup with birth year in the future (должна быть ошибка)."""
        payload = {
            "email": "future_birth@example.com",
            "password": "SecurePass123",
            "birth": 2050,  # Будущий год
        }

        resp = await client.post("/api/auth/signup", json=payload)
        assert resp.status_code == 422
        error = resp.json()
        assert "detail" in error

    async def test_signup_birth_too_old(self, client: AsyncClient):
        """Test signup with birth year < 1900 (должна быть ошибка)."""
        payload = {
            "email": "old_birth@example.com",
            "password": "SecurePass123",
            "birth": 1850,  # Раньше 1900
        }

        resp = await client.post("/api/auth/signup", json=payload)
        assert resp.status_code == 422

    async def test_signup_cor_id_ignored(self, client: AsyncClient):
        """
        Test that cor_id in request body is ignored.
        COR-ID должен генерироваться автоматически, а не приниматься из запроса.
        """
        payload = {
            "email": "cor_id_test@example.com",
            "password": "SecurePass123",
            "cor_id": "CUSTOM_COR_ID_12345",  # Должно быть проигнорировано
        }

        resp = await client.post("/api/auth/signup", json=payload)
        # Должен быть успех, а не 500 ошибка
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # COR-ID должен быть сгенерирован системой, а не взят из запроса
        assert data["user"]["cor_id"] is not None
        assert data["user"]["cor_id"] != "CUSTOM_COR_ID_12345"

    async def test_signup_duplicate_email(self, client: AsyncClient):
        """Test signup with already existing email."""
        email = "duplicate@example.com"
        payload = {
            "email": email,
            "password": "SecurePass123",
        }

        # Первая регистрация
        resp1 = await client.post("/api/auth/signup", json=payload)
        assert resp1.status_code == 200

        # Вторая регистрация с тем же email
        resp2 = await client.post("/api/auth/signup", json=payload)
        assert resp2.status_code == 409  # Conflict
        assert resp2.json()["detail"] == "Account already exists"

    async def test_signup_password_too_short(self, client: AsyncClient):
        """Test signup with password < 8 characters."""
        payload = {
            "email": "short_pass@example.com",
            "password": "Short1",  # Меньше 8 символов
        }

        resp = await client.post("/api/auth/signup", json=payload)
        assert resp.status_code == 422

    async def test_signup_password_too_long(self, client: AsyncClient):
        """Test signup with password > 32 characters."""
        payload = {
            "email": "long_pass@example.com",
            "password": "A" * 40,  # Больше 32 символов
        }

        resp = await client.post("/api/auth/signup", json=payload)
        assert resp.status_code == 422

    async def test_signup_invalid_email(self, client: AsyncClient):
        """Test signup with invalid email format."""
        payload = {
            "email": "not-an-email",
            "password": "SecurePass123",
        }

        resp = await client.post("/api/auth/signup", json=payload)
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestLogin:
    """Test user login endpoint /auth/login."""

    async def test_login_success(self, client: AsyncClient, db_session: AsyncSession):
        """Test successful login with correct credentials."""
        # Сначала создаём пользователя
        signup_payload = {
            "email": "login_test@example.com",
            "password": "LoginPass123",
        }
        signup_resp = await client.post("/api/auth/signup", json=signup_payload)
        assert signup_resp.status_code == 200

        # Теперь логинимся
        login_payload = {
            "username": "login_test@example.com",  # OAuth2 использует "username"
            "password": "LoginPass123",
        }
        resp = await client.post(
            "/api/auth/login",
            data=login_payload,  # OAuth2PasswordRequestForm использует form data
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "session_id" in data
        assert "device_id" in data

    async def test_login_wrong_password(self, client: AsyncClient):
        """Test login with wrong password."""
        # Создаём пользователя
        signup_payload = {
            "email": "wrong_pass@example.com",
            "password": "CorrectPass123",
        }
        await client.post("/api/auth/signup", json=signup_payload)

        # Логинимся с неправильным паролем
        login_payload = {
            "username": "wrong_pass@example.com",
            "password": "WrongPassword",
        }
        resp = await client.post(
            "/api/auth/login",
            data=login_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent email."""
        login_payload = {
            "username": "nonexistent@example.com",
            "password": "SomePassword123",
        }
        resp = await client.post(
            "/api/auth/login",
            data=login_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 401

    async def test_login_missing_credentials(self, client: AsyncClient):
        """Test login with missing credentials."""
        login_payload = {
            "username": "user@example.com",
            # Нет password
        }
        resp = await client.post(
            "/api/auth/login",
            data=login_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 422
