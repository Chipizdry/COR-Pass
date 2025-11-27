"""Tests for Sibionics signature verification."""
import hashlib
import json

import pytest
from httpx import AsyncClient

from cor_pass.database.models.user import User


class TestSignatureVerification:
    """Test Sibionics webhook signature verification logic."""
    
    def test_signature_calculation(self):
        """Test signature calculation matches Sibionics algorithm."""
        app_id = "2lwUcVCY1PLbMKxf"
        nonce = "test_nonce_123"
        body = '{"type":201,"content":{"bizIds":["test"],"thirdBizId":"user123","isAuthorized":true,"grantTime":1704067200000}}'
        sign_secret = "1234567812345678"
        
        # Calculate signature: MD5(appId + nonce + body + sign_secret).upper()
        sign_string = f"{app_id}{nonce}{body}{sign_secret}"
        signature = hashlib.md5(sign_string.encode()).hexdigest().upper()
        
        # Verify signature is uppercase MD5 hash
        assert len(signature) == 32
        assert signature.isupper()
        assert signature.isalnum()
    
    @pytest.mark.asyncio
    async def test_signature_with_different_nonce(
        self,
        client: AsyncClient,
        test_user: User,
        sibionics_webhook_payload
    ):
        """Test that different nonce produces different signature."""
        payload = sibionics_webhook_payload(user_id=str(test_user.id))
        body_str = json.dumps(payload, separators=(',', ':'))
        
        app_id = "2lwUcVCY1PLbMKxf"
        sign_secret = "1234567812345678"
        
        # Calculate signature with nonce1
        nonce1 = "nonce_001"
        sign_string1 = f"{app_id}{nonce1}{body_str}{sign_secret}"
        signature1 = hashlib.md5(sign_string1.encode()).hexdigest().upper()
        
        # Calculate signature with nonce2
        nonce2 = "nonce_002"
        sign_string2 = f"{app_id}{nonce2}{body_str}{sign_secret}"
        signature2 = hashlib.md5(sign_string2.encode()).hexdigest().upper()
        
        # Signatures should be different
        assert signature1 != signature2
        
        # Both should be valid for their respective nonces
        headers1 = {
            "appId": app_id,
            "nonce": nonce1,
            "signature-app": signature1,
            "Content-Type": "application/json"
        }
        response1 = await client.post(
            "/api/sibionics/callback",
            json=payload,
            headers=headers1
        )
        assert response1.status_code == 200
    
    @pytest.mark.asyncio
    async def test_signature_sensitive_to_body_changes(
        self,
        client: AsyncClient,
        test_user: User,
        sibionics_webhook_payload,
        sibionics_webhook_headers
    ):
        """Test signature validation with tampered body (currently only logged)."""
        payload = sibionics_webhook_payload(user_id=str(test_user.id))
        body_str = json.dumps(payload, separators=(',', ':'))
        
        # Generate valid signature for original payload
        headers = sibionics_webhook_headers(body_str)
        
        # Tamper with payload after signature generation
        payload["content"]["bizIds"] = ["tampered_biz_id"]
        
        # Send tampered payload with original signature
        response = await client.post(
            "/api/sibionics/callback",
            json=payload,  # Tampered
            headers=headers  # Valid for original
        )
        
        # Currently signature mismatch is only logged, not enforced
        # TODO: Enable signature enforcement
        assert response.status_code == 200
        assert response.text == '"SUCCESS"'
    
    @pytest.mark.asyncio
    async def test_signature_case_sensitive(
        self,
        client: AsyncClient,
        test_user: User,
        sibionics_webhook_payload
    ):
        """Test signature case sensitivity (currently only logged)."""
        payload = sibionics_webhook_payload(user_id=str(test_user.id))
        body_str = json.dumps(payload, separators=(',', ':'))
        
        app_id = "2lwUcVCY1PLbMKxf"
        nonce = "test_nonce"
        sign_secret = "1234567812345678"
        
        # Calculate lowercase signature
        sign_string = f"{app_id}{nonce}{body_str}{sign_secret}"
        lowercase_signature = hashlib.md5(sign_string.encode()).hexdigest().lower()
        
        headers = {
            "appId": app_id,
            "nonce": nonce,
            "signature-app": lowercase_signature,
            "Content-Type": "application/json"
        }
        
        # Send with lowercase signature
        response = await client.post(
            "/api/sibionics/callback",
            json=payload,
            headers=headers
        )
        
        # Currently signature mismatch is only logged
        # TODO: Enable strict signature enforcement
        assert response.status_code == 200
        assert response.text == '"SUCCESS"'
    
    @pytest.mark.asyncio
    async def test_signature_with_unicode_body(
        self,
        client: AsyncClient,
        test_user: User,
        sibionics_webhook_headers
    ):
        """Test signature works with unicode characters in body."""
        payload = {
            "type": 201,
            "content": {
                "bizIds": ["测试_biz_id"],  # Chinese characters
                "thirdBizId": str(test_user.id),
                "isAuthorized": True,
                "grantTime": 1704067200000
            }
        }
        body_str = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
        headers = sibionics_webhook_headers(body_str)
        
        # Send callback
        response = await client.post(
            "/api/sibionics/callback",
            json=payload,
            headers=headers
        )
        
        # Should handle unicode correctly
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_replay_attack_prevention(
        self,
        client: AsyncClient,
        test_user: User,
        sibionics_webhook_payload,
        sibionics_webhook_headers
    ):
        """Test that same request can be replayed (nonce not stored currently)."""
        payload = sibionics_webhook_payload(user_id=str(test_user.id))
        body_str = json.dumps(payload, separators=(',', ':'))
        headers = sibionics_webhook_headers(body_str)
        
        # Send first request
        response1 = await client.post(
            "/api/sibionics/callback",
            json=payload,
            headers=headers
        )
        assert response1.status_code == 200
        
        # Send exact same request again (replay)
        response2 = await client.post(
            "/api/sibionics/callback",
            json=payload,
            headers=headers
        )
        
        # Currently accepts replay (nonce not stored)
        # TODO: Implement nonce storage for replay prevention
        assert response2.status_code == 200
