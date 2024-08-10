import asyncio
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
import hashlib
import secrets

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
import os
import base64
from Crypto.Util.Padding import pad as crypto_pad

from cor_pass.config.config import settings


from Crypto.Util.Padding import pad, unpad


def pad(data: bytes, block_size: int) -> bytes:
    if isinstance(data, str):
        data = data.encode()
    return crypto_pad(data, block_size)


async def encrypt_data(data: bytes, key: bytes) -> bytes:
    aes_key = key
    cipher = AES.new(aes_key, AES.MODE_CBC)
    encrypted_data = cipher.encrypt(pad(data, AES.block_size))
    encoded_data = base64.b64encode(cipher.iv + encrypted_data)
    return encoded_data


async def decrypt_data(encrypted_data: bytes, key: bytes) -> str:
    aes_key = key
    decoded_data = base64.b64decode(encrypted_data)
    iv = decoded_data[: AES.block_size]
    ciphertext = decoded_data[AES.block_size :]

    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    decrypted_data = unpad(cipher.decrypt(ciphertext), AES.block_size)
    return decrypted_data.decode()


async def generate_aes_key(key: bytes) -> bytes:
    random_key = secrets.token_urlsafe(16)
    sha256 = hashlib.sha256()
    sha256.update(random_key.encode())
    aes_key = sha256.digest()[:16]
    return aes_key


async def encrypt_user_key(key: bytes) -> str:
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend(),
    )
    aes_key = await asyncio.to_thread(kdf.derive, settings.aes_key.encode())

    cipher = Fernet(base64.urlsafe_b64encode(aes_key))
    encrypted_key = cipher.encrypt(key)
    return base64.urlsafe_b64encode(salt + encrypted_key).decode()


async def decrypt_user_key(encrypted_key: str) -> bytes:
    encrypted_data = base64.urlsafe_b64decode(encrypted_key)
    salt = encrypted_data[:16]
    ciphertext = encrypted_data[16:]

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend(),
    )
    aes_key = await asyncio.to_thread(kdf.derive, settings.aes_key.encode())

    cipher = Fernet(base64.urlsafe_b64encode(aes_key))
    return cipher.decrypt(ciphertext)
