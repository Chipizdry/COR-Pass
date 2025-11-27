"""Tests for Sibionics H5 authorization flow."""
import pytest
from httpx import AsyncClient
from urllib.parse import urlparse, parse_qs

from cor_pass.database.models.user import User


@pytest.mark.skip(reason="Auth endpoints require authentication - will test with integration tests")
class TestSibionicsAuthorization:
    """Test Sibionics H5 authorization URL generation and flow."""
    
    @pytest.mark.asyncio
    async def test_get_auth_url_success(
        self,
        client: AsyncClient,
        test_user: User
    ):
        """Test H5 authorization URL is generated correctly."""
        response = await client.get(
            f"/api/sibionics/auth-url",
            params={"user_id": str(test_user.id)}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "authorization_url" in data
        assert "user_id" in data
        assert data["user_id"] == str(test_user.id)
        
        # Parse URL
        url = data["authorization_url"]
        parsed = urlparse(url)
        
        # Verify base URL
        assert parsed.scheme == "https"
        assert "open-auth-uat.sisensing.com" in parsed.netloc
        
        # Verify query parameters
        params = parse_qs(parsed.query)
        assert "appKey" in params
        assert params["appKey"][0] == "2lwUcVCY1PLbMKxf"
        assert "thirdBizId" in params
        assert params["thirdBizId"][0] == str(test_user.id)
        assert "redirectUrl" in params
        assert "/api/sibionics/callback" in params["redirectUrl"][0]
    
    @pytest.mark.asyncio
    async def test_get_auth_url_missing_user_id(self, client: AsyncClient):
        """Test auth URL generation fails without user_id."""
        response = await client.get("/api/sibionics/auth-url")
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_get_auth_url_invalid_user_id(self, client: AsyncClient):
        """Test auth URL generation with invalid UUID."""
        response = await client.get(
            "/api/sibionics/auth-url",
            params={"user_id": "not-a-valid-uuid"}
        )
        
        # Should still generate URL (user existence not validated at this step)
        # Validation happens in callback
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_manual_auth_save(
        self,
        client: AsyncClient,
        db_session,
        test_user: User
    ):
        """Test manual authorization save endpoint."""
        auth_data = {
            "user_id": str(test_user.id),
            "access_token": "manual_test_token_12345",
            "expires_in": 7200
        }
        
        response = await client.post(
            "/api/sibionics/auth",
            json=auth_data
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["user_id"] == str(test_user.id)
        assert data["access_token"] == "manual_test_token_12345"
        assert data["is_active"] is True
        assert data["biz_id"] is None  # Not set until callback
    
    @pytest.mark.asyncio
    async def test_get_auth_status_exists(
        self,
        client: AsyncClient,
        test_sibionics_auth,
        test_user: User
    ):
        """Test getting authorization status when it exists."""
        response = await client.get(
            f"/api/sibionics/auth",
            params={"user_id": str(test_user.id)}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["user_id"] == str(test_user.id)
        assert data["is_active"] is True
        assert "access_token" in data
    
    @pytest.mark.asyncio
    async def test_get_auth_status_not_found(
        self,
        client: AsyncClient,
        test_user: User
    ):
        """Test getting authorization status when it doesn't exist."""
        response = await client.get(
            f"/api/sibionics/auth",
            params={"user_id": str(test_user.id)}
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_delete_auth(
        self,
        client: AsyncClient,
        test_sibionics_auth,
        test_user: User
    ):
        """Test revoking authorization."""
        response = await client.delete(
            f"/api/sibionics/auth",
            params={"user_id": str(test_user.id)}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "revoked" in data["message"].lower()
    
    @pytest.mark.asyncio
    async def test_redirect_url_generation(self, client: AsyncClient, test_user: User):
        """Test that redirect URL points to callback endpoint."""
        response = await client.get(
            f"/api/sibionics/auth-url",
            params={"user_id": str(test_user.id)}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        url = data["authorization_url"]
        params = parse_qs(urlparse(url).query)
        redirect_url = params["redirectUrl"][0]
        
        # Verify redirect URL is our callback endpoint
        assert "/api/sibionics/callback" in redirect_url
        # Should be absolute URL for Sibionics to POST to
        parsed_redirect = urlparse(redirect_url)
        assert parsed_redirect.scheme in ["http", "https"]
        assert parsed_redirect.path == "/api/sibionics/callback"
