import pyotp
import requests
import time


def generate_and_verify_otp(secret: str):

    totp = pyotp.TOTP(secret)
    otp = totp.now()
    time_remaining = totp.interval - (time.time() % totp.interval)
    print(f"Generated OTP: {otp}")

    return otp, time_remaining
