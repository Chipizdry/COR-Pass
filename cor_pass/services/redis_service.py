from cor_pass.database.redis_db import redis_client

from datetime import timedelta


async def add_jti_to_blacklist(jti: str, expires_delta: timedelta):
    """
    Добавляет JTI в черный список Redis с установленным сроком жизни.
    """
    await redis_client.setex(f"blacklist:{jti}", int(expires_delta.total_seconds()), 1)


async def is_jti_blacklisted(jti: str) -> bool:
    """
    Проверяет, находится ли JTI в черном списке Redis.
    """
    return await redis_client.exists(f"blacklist:{jti}")
