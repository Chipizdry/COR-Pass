"""Tests for Sibionics webhook callback endpoint."""
import json
import hashlib
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.database.models.user import User
from cor_pass.database.models.health import SibionicsAuth


class TestSibionicsCallback:
    """Test Sibionics authorization callback webhook."""
    
    @pytest.mark.asyncio
    async def test_callback_success_new_authorization(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        sibionics_webhook_payload,
        sibionics_webhook_headers
    ):
        """Test successful webhook callback for new authorization."""
        # Prepare payload
        payload = sibionics_webhook_payload(
            user_id=str(test_user.id),
            biz_ids=["biz_id_001", "biz_id_002"]
        )
        body_str = json.dumps(payload, separators=(',', ':'))
        headers = sibionics_webhook_headers(body_str)
        
        # Send callback
        response = await client.post(
            "/api/sibionics/callback",
            json=payload,
            headers=headers
        )
        
        # Debug: print error if not 200
        if response.status_code != 200:
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        
        # Verify response
        assert response.status_code == 200
        assert response.text == '"SUCCESS"'
        
        # Verify database record created
        result = await db_session.execute(
            select(SibionicsAuth).where(SibionicsAuth.user_id == test_user.id)
        )
        auth = result.scalar_one()
        assert auth.biz_id == "biz_id_001"  # First biz_id used as primary
        assert auth.is_active is True
    
    @pytest.mark.asyncio
    async def test_callback_success_update_existing(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_sibionics_auth: SibionicsAuth,
        test_user: User,
        sibionics_webhook_payload,
        sibionics_webhook_headers
    ):
        """Test webhook callback updates existing authorization."""
        # Prepare payload
        payload = sibionics_webhook_payload(
            user_id=str(test_user.id),
            biz_ids=["new_biz_id_123"]
        )
        body_str = json.dumps(payload, separators=(',', ':'))
        headers = sibionics_webhook_headers(body_str)
        
        # Send callback
        response = await client.post(
            "/api/sibionics/callback",
            json=payload,
            headers=headers
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.text == '"SUCCESS"'
        
        # Verify database record updated
        await db_session.refresh(test_sibionics_auth)
        assert test_sibionics_auth.biz_id == "new_biz_id_123"
        assert test_sibionics_auth.is_active is True
    
    @pytest.mark.asyncio
    async def test_callback_unauthorized_deactivates(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_sibionics_auth: SibionicsAuth,
        test_user: User,
        sibionics_webhook_payload,
        sibionics_webhook_headers
    ):
        """Test webhook with isAuthorized=false returns SUCCESS (deactivation not implemented yet)."""
        # Prepare payload with unauthorized status
        payload = sibionics_webhook_payload(
            user_id=str(test_user.id),
            is_authorized=False
        )
        body_str = json.dumps(payload, separators=(',', ':'))
        headers = sibionics_webhook_headers(body_str)
        
        # Send callback
        response = await client.post(
            "/api/sibionics/callback",
            json=payload,
            headers=headers
        )
        
        # Verify response (still SUCCESS to prevent retries)
        assert response.status_code == 200
        assert response.text == '"SUCCESS"'
        
        # TODO: Implement deactivation logic in endpoint
        # Currently endpoint only logs warning and returns SUCCESS
        # Authorization should remain active until deactivation is implemented
        await db_session.refresh(test_sibionics_auth)
        assert test_sibionics_auth.is_active is True  # Not deactivated yet
    
    @pytest.mark.asyncio
    async def test_callback_invalid_signature(
        self,
        client: AsyncClient,
        test_user: User,
        sibionics_webhook_payload
    ):
        """Test webhook with invalid signature is logged but not rejected (signature check commented out)."""
        payload = sibionics_webhook_payload(user_id=str(test_user.id))
        body_str = json.dumps(payload, separators=(',', ':'))
        
        # Create headers with wrong signature
        headers = {
            "appId": "2lwUcVCY1PLbMKxf",
            "nonce": "test_nonce",
            "signature-app": "INVALID_SIGNATURE_12345",
            "Content-Type": "application/json"
        }
        
        # Send callback
        response = await client.post(
            "/api/sibionics/callback",
            json=payload,
            headers=headers
        )
        
        # Currently signature verification is only logged, not enforced
        # TODO: Enable signature enforcement in production
        assert response.status_code == 200
        assert response.text == '"SUCCESS"'
    
    @pytest.mark.asyncio
    async def test_callback_missing_headers(
        self,
        client: AsyncClient,
        test_user: User,
        sibionics_webhook_payload
    ):
        """Test webhook with missing headers still works (headers are optional)."""
        payload = sibionics_webhook_payload(user_id=str(test_user.id))
        
        # Send callback without signature headers
        response = await client.post(
            "/api/sibionics/callback",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Headers are optional, endpoint should still process
        assert response.status_code == 200
        assert response.text == '"SUCCESS"'
    
    @pytest.mark.asyncio
    async def test_callback_wrong_webhook_type(
        self,
        client: AsyncClient,
        test_user: User,
        sibionics_webhook_headers
    ):
        """Test webhook with wrong type fails validation."""
        payload = {
            "type": 20903,  # Glucose data event, not 201
            "content": {"some": "data"}  # Wrong content structure
        }
        body_str = json.dumps(payload, separators=(',', ':'))
        headers = sibionics_webhook_headers(body_str)
        
        # Send callback
        response = await client.post(
            "/api/sibionics/callback",
            json=payload,
            headers=headers
        )
        
        # Wrong content structure fails Pydantic validation
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_callback_user_not_found(
        self,
        client: AsyncClient,
        sibionics_webhook_payload,
        sibionics_webhook_headers
    ):
        """Test webhook for non-existent user returns SUCCESS to prevent retries."""
        # Use random UUID that doesn't exist
        fake_user_id = str(uuid4())
        payload = sibionics_webhook_payload(user_id=fake_user_id)
        body_str = json.dumps(payload, separators=(',', ':'))
        headers = sibionics_webhook_headers(body_str)
        
        # Send callback
        response = await client.post(
            "/api/sibionics/callback",
            json=payload,
            headers=headers
        )
        
        # Endpoint returns SUCCESS for 404 to prevent endless retries
        assert response.status_code == 200
        assert response.text == '"SUCCESS"'
    
    @pytest.mark.asyncio
    async def test_callback_empty_biz_ids(
        self,
        client: AsyncClient,
        test_user: User,
        sibionics_webhook_payload,
        sibionics_webhook_headers
    ):
        """Test webhook with empty bizIds array returns error."""
        payload = sibionics_webhook_payload(
            user_id=str(test_user.id),
            biz_ids=[]
        )
        body_str = json.dumps(payload, separators=(',', ':'))
        headers = sibionics_webhook_headers(body_str)
        
        # Send callback
        response = await client.post(
            "/api/sibionics/callback",
            json=payload,
            headers=headers
        )
        
        # Empty bizIds should return error (400 Bad Request)
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_callback_multiple_biz_ids(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        sibionics_webhook_payload,
        sibionics_webhook_headers
    ):
        """Test webhook with multiple bizIds uses first as primary."""
        biz_ids = ["primary_biz_id", "secondary_biz_id", "tertiary_biz_id"]
        payload = sibionics_webhook_payload(
            user_id=str(test_user.id),
            biz_ids=biz_ids
        )
        body_str = json.dumps(payload, separators=(',', ':'))
        headers = sibionics_webhook_headers(body_str)
        
        # Send callback
        response = await client.post(
            "/api/sibionics/callback",
            json=payload,
            headers=headers
        )
        
        assert response.status_code == 200
        
        # Verify first biz_id is primary
        result = await db_session.execute(
            select(SibionicsAuth).where(SibionicsAuth.user_id == test_user.id)
        )
        auth = result.scalar_one()
        assert auth.biz_id == "primary_biz_id"
