# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker


# SQLALCHEMY_DATABASE_URL = settings.sqlalchemy_database_url

# engine = create_engine(SQLALCHEMY_DATABASE_URL)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# # Dependency
# def get_db():
#     """
#     The get_db function opens a new database connection if there is none yet for the current application context.
#     It will also create the database tables if they don't exist yet.

#     :return: A sessionlocal instance
#     """
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


from cor_pass.config.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URL = settings.sqlalchemy_database_url

engine = create_async_engine(SQLALCHEMY_DATABASE_URL)
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
