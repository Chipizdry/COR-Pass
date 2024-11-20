from redis import Redis
from cor_pass.config.config import settings


redis_client = Redis(
    host=settings.redis_host, port=settings.redis_port, db=settings.redis_db
)
