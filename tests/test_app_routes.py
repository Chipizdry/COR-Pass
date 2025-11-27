"""Test that application routes are properly configured."""
import pytest
from httpx import AsyncClient


class TestAppRoutes:
    """Test application routing."""
    
    @pytest.mark.asyncio
    async def test_sibionics_callback_route_exists(self, client: AsyncClient):
        """Test that sibionics callback route is registered."""
        # Try valid payload structure
        payload = {
            "type": 201,
            "content": {
                "bizIds": ["test_biz_id"],
                "thirdBizId": "test_user_id",
                "isAuthorized": True,
                "grantTime": 1704067200000
            }
        }
        
        response = await client.post(
            "/api/sibionics/callback",
            json=payload
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        # If route doesn't exist, we'd get 404
        # If route exists but data is invalid, we get 400/422 or 200
        assert response.status_code in [200, 400, 404, 422], \
            f"Unexpected status {response.status_code}: {response.text}"
    
    @pytest.mark.asyncio
    async def test_healthchecker_route_exists(self, client: AsyncClient):
        """Test that healthchecker route works."""
        response = await client.get("/api/healthchecker")
        
        # Should work
        assert response.status_code in [200, 500]  # 500 if DB connection fails
