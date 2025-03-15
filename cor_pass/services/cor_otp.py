import pyotp
import time
from cor_pass.services.cipher import decrypt_data, decrypt_user_key
from cor_pass.database.models import User
from cor_pass.services.logger import logger
from fastapi import HTTPException, status


async def generate_and_verify_otp(secret: bytes, user: User):
    try:
        secret = await decrypt_data(
            encrypted_data=secret, key=await decrypt_user_key(user.unique_cipher_key)
        )
        totp = pyotp.TOTP(secret)
        otp = totp.now()
        time_remaining = totp.interval - (time.time() % totp.interval)
        print(f"Generated OTP: {otp}")

        return otp, time_remaining
    except Exception as e:
        logger.error(f"Failed to verify otp: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to verify otp"
        )
