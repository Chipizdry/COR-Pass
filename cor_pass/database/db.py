from cor_pass.config.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URL = settings.sqlalchemy_database_url

POOL_SIZE = 10  
MAX_OVERFLOW = 30 

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=60,
    pool_pre_ping=True,
    pool_recycle=3600
)
# engine = create_async_engine(SQLALCHEMY_DATABASE_URL)
# Base = declarative_base()
async_session_maker = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    """
    Функция get_db открывает новое асинхронное подключение к базе данных
    если для текущего контекста программы ещё такового нет.
    После завершения запроса подключение закрывается.

    :return: Асинхронный обьект сессии AsyncSession
    """
    async with async_session_maker() as session:
        yield session
