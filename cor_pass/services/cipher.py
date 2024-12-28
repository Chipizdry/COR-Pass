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
    """
    Эта функция добавляет необходимое количество байтов к данным, чтобы они соответствовали размеру блока. Если данные являются строкой, они сначала кодируются в байты.
    Параметры:
    data: данные для дополнения (в байтах).
    block_size: размер блока, к которому нужно дополнить данные.
    Возвращает: дополненные данные.
    """
    if isinstance(data, str):
        data = data.encode()
    return crypto_pad(data, block_size)


async def encrypt_data(data: bytes, key: bytes) -> bytes:
    """
    Эта асинхронная функция шифрует данные с использованием AES в режиме CBC.

    Параметры:
    data: данные для шифрования (в байтах).
    key: ключ шифрования (в байтах).
    Процесс:
    Генерируется вектор инициализации (IV).
    Данные шифруются.
    IV и зашифрованные данные кодируются в Base64 и возвращаются.
    """
    aes_key = key
    cipher = AES.new(aes_key, AES.MODE_CBC)
    encrypted_data = cipher.encrypt(pad(data, AES.block_size))
    encoded_data = base64.b64encode(cipher.iv + encrypted_data)
    return encoded_data


async def decrypt_data(encrypted_data: bytes, key: bytes) -> str:
    """
    Эта асинхронная функция дешифрует данные, зашифрованные функцией encrypt_data.

    Параметры:
    encrypted_data: зашифрованные данные (в байтах).
    key: ключ шифрования (в байтах).
    Процесс:
    Данные декодируются из Base64.
    Извлекается IV и зашифрованные данные.
    Данные дешифруются и возвращаются в виде строки.
    """
    aes_key = key
    decoded_data = base64.b64decode(encrypted_data)
    iv = decoded_data[: AES.block_size]
    ciphertext = decoded_data[AES.block_size :]

    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    decrypted_data = unpad(cipher.decrypt(ciphertext), AES.block_size)
    return decrypted_data.decode()


async def generate_aes_key() -> bytes:
    """
    Эта функция генерирует новый ключ для AES.

    Процесс:
    Генерируется случайный ключ с помощью secrets.token_urlsafe.
    Ключ хешируется с использованием SHA256 и обрезается до 16 байт.
    Возвращает: ключ AES (в байтах).
    """
    random_key = secrets.token_urlsafe(16)
    sha256 = hashlib.sha256()
    sha256.update(random_key.encode())
    aes_key = sha256.digest()[:16]
    return aes_key


async def generate_recovery_code():
    """
    Эта функция генерирует код восстановления.

    Процесс:
    Генерируется случайный ключ с помощью secrets.token_urlsafe.
    Ключ хешируется с использованием SHA256 и обрезается до 64 символов.
    Возвращает: код восстановления (в виде строки).
    """
    random_key = secrets.token_urlsafe(64)
    sha256 = hashlib.sha256()
    sha256.update(random_key.encode())
    recovery_code = sha256.hexdigest()[:64]
    return recovery_code


async def encrypt_user_key(key: bytes) -> str:
    """
    Эта функция шифрует пользовательский ключ.

    Параметры:
    key: ключ пользователя (в байтах).
    Процесс:
    Генерируется случайная "соль".
    Производится KDF (Key Derivation Function) с использованием PBKDF2HMAC.
    Ключ шифруется с использованием Fernet и кодируется в Base64.
    Возвращает: зашифрованный ключ пользователя (в виде строки).
    """
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
    """
    Эта функция дешифрует зашифрованный пользовательский ключ.

    Параметры:
    encrypted_key: зашифрованный ключ пользователя (в виде строки).
    Процесс:
    Декодируется ключ из Base64.
    Извлекается соль и зашифрованный текст.
    Производится KDF для получения AES-ключа.
    Данные дешифруются и возвращаются.
    Возвращает: расшифрованный пользовательский ключ (в байтах).
    """
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
