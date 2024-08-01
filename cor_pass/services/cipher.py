from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
import hashlib
import secrets


def encrypt_data(data, key):
    aes_key = key
    cipher = AES.new(aes_key, AES.MODE_CBC)
    encrypted_data = cipher.encrypt(pad(data.encode(), AES.block_size))
    encoded_data = base64.b64encode(cipher.iv + encrypted_data)
    return encoded_data


def decrypt_data(encrypted_data, key):
    aes_key = key
    decoded_data = base64.b64decode(encrypted_data)
    iv = decoded_data[: AES.block_size]
    ciphertext = decoded_data[AES.block_size :]

    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    decrypted_data = unpad(cipher.decrypt(ciphertext), AES.block_size)
    return decrypted_data.decode()


def generate_aes_key(key):
    random_key = secrets.token_urlsafe(16)
    sha256 = hashlib.sha256()
    sha256.update(random_key.encode())
    aes_key = sha256.digest()[:16]
    return aes_key
