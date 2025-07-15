import logging
import sys
from loguru import logger
from cor_pass.config.config import settings 

class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())

def setup_logging():
    logger.remove()

    log_level = "DEBUG" if settings.debug else "INFO"

    logger.add(
        sys.stdout,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=log_level
    )

    logging.basicConfig(handlers=[InterceptHandler()], level=0)


    logging.getLogger("gunicorn").handlers = [InterceptHandler()]
    logging.getLogger("gunicorn").propagate = False
    logging.getLogger("gunicorn").setLevel(log_level)

    logging.getLogger("gunicorn.access").handlers = [InterceptHandler()]
    logging.getLogger("gunicorn.access").propagate = False
    logging.getLogger("gunicorn.access").setLevel(log_level)

    logging.getLogger("gunicorn.error").handlers = [InterceptHandler()]
    logging.getLogger("gunicorn.error").propagate = False
    logging.getLogger("gunicorn.error").setLevel(log_level)

    logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]
    logging.getLogger("uvicorn.access").propagate = False
    logging.getLogger("uvicorn.access").setLevel(log_level)

    logging.getLogger("uvicorn.error").handlers = [InterceptHandler()]
    logging.getLogger("uvicorn.error").propagate = False
    logging.getLogger("uvicorn.error").setLevel(log_level)
    
    logging.getLogger("pymodbus.logging").setLevel(logging.INFO)

    logging.getLogger("passlib.handlers.bcrypt").setLevel(logging.ERROR) 
