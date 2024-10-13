from io import BytesIO


from cor_pass.config.config import settings


encryption_key = settings.encryption_key


async def generate_recovery_file(recovery_code: str):

    encrypted_code = recovery_code.encode()  # Код без шифрования
    # Создание бинарного файла с зашифрованным кодом
    encrypted_file = BytesIO(encrypted_code)
    encrypted_file.name = "recovery_key.bin"
    return encrypted_file
