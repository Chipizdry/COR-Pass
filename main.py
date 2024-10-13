import time

import uvicorn
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import FastAPI, Request, Depends, HTTPException, status, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import hashlib
import hmac
from prometheus_client import Counter, Histogram
from prometheus_client import generate_latest
from starlette.responses import Response

from cor_pass.routes import auth, person
from cor_pass.database.db import get_db
from cor_pass.routes import (
    auth,
    records,
    tags,
    password_generator,
    cor_id,
    otp_auth,
    admin,
)
from cor_pass.config.config import settings
from cor_pass.services.logger import logger
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from collections import defaultdict


from datetime import datetime, timedelta


app = FastAPI()
app.mount("/static", StaticFiles(directory="cor_pass/static"), name="static")

origins = [
    "http://192.168.153.203:8000" "http://localhost:3000",
    "http://192.168.153.21:3000",
]


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")


# Пример метрик
REQUEST_COUNT = Counter("app_requests_total", "Total number of requests")
REQUEST_LATENCY = Histogram("app_request_latency_seconds", "Request latency")

# Middleware для CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Обработчики исключений
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    logger.error("An unhandled exception occurred", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error("Request validation error", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation Error"},
    )


# Маршруты
@app.get("/config")
def read_config():
    return {"ENV": settings.app_env}


@app.get("/", name="Корень")
def read_root(request: Request):
    logger.info("This is a test log message")
    REQUEST_COUNT.inc()
    with REQUEST_LATENCY.time():
        return FileResponse("cor_pass/static/login.html")


@app.get("/api/healthchecker")
def healthchecker(db: Session = Depends(get_db)):
    REQUEST_COUNT.inc()
    try:
        result = db.execute(text("SELECT 1")).fetchone()
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Database is not configured correctly",
            )
        return {"message": "Welcome to FastApi, database work correctly"}
    except Exception as e:
        logger.error("Database connection error", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error connecting to the database",
        )


# Middleware для добавления заголовка времени обработки
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["My-Process-Time"] = str(process_time)
    return response


# Событие при старте приложения
@app.on_event("startup")
async def startup():
    print("------------- STARTUP --------------")


auth_attempts = defaultdict(list)
blocked_ips = {}


# @app.middleware("http")
# async def auth_attempt_middleware(request: Request, call_next):
#     # Получите IP-адрес клиента
#     client_ip = request.client.host

#     try:
#         # Выполните авторизацию
#         response = await call_next(request)
#     except HTTPException as e:
#         if e.status_code == 401:  # Неудачная авторизация
#             # Добавьте попытку авторизации в словарь
#             auth_attempts[client_ip].append(datetime.now())
#             print(client_ip)
#             print("client_ip")
#             # Проверьте, не заблокирован ли этот IP-адрес
#             if client_ip in blocked_ips and blocked_ips[client_ip] > datetime.now():
#                 raise HTTPException(status_code=429, detail="IP-адрес заблокирован")

#             # Проверьте, если было 5 неудачных попыток за последние 15 минут
#             if len(auth_attempts[client_ip]) >= 5 and auth_attempts[client_ip][
#                 -1
#             ] - auth_attempts[client_ip][0] <= timedelta(minutes=15):
#                 # Заблокируйте IP-адрес на 15 минут
#                 blocked_ips[client_ip] = datetime.now() + timedelta(minutes=15)
#                 raise HTTPException(
#                     status_code=429,
#                     detail="Слишком много попыток авторизации, IP-адрес заблокирован на 15 минут",
#                 )

#         # Если произошло что-то другое, просто вернем исключение
#         raise e

#     return response


app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(records.router, prefix="/api")
app.include_router(tags.router, prefix="/api")
app.include_router(password_generator.router, prefix="/api")
app.include_router(person.router, prefix="/api")
app.include_router(cor_id.router, prefix="/api")
app.include_router(otp_auth.router, prefix="/api")


if __name__ == "__main__":
    uvicorn.run(
        app="main:app", host="192.168.153.203", port=8000, reload=settings.reload
    )
# 192.168.153.203
