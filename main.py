import asyncio
import time
import uvicorn
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from fastapi import FastAPI, Request, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import Counter, Histogram, CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest, multiprocess

from prometheus_fastapi_instrumentator import PrometheusFastApiInstrumentator

from starlette.middleware.trustedhost import TrustedHostMiddleware


from fastapi_limiter import FastAPILimiter


from cor_pass.repository.cerbo_service import (
    close_modbus_client,
    create_modbus_client,
)
from cor_pass.version import __version__
from cor_pass.routes import auth, person
from cor_pass.database.db import get_db, async_session_maker
from cor_pass.database.redis_db import redis_client
from cor_pass.services.websocket_events_manager import websocket_events_manager
from cor_pass.routes import (
    auth,
    records,
    password_generator,
    cor_id,
    otp_auth,
    admin,
    lawyer,
    financier,
    doctor,
    websocket,
    device_ws,
    device_proxy,
    cases,
    samples,
    cassettes,
    glasses,
    dicom_router,
    printing_device,
    printer,
    websocket_events,
    svs_router,
    lab_assistants,
    energy_managers,
    cerbo_routes,
    blood_pressures,
    ecg_measurements,
    excel_router,
    scanner_router,
    medicines,
    first_aid_kits,
    support,
    ophthalmological_prescriptions,
    prescriptions,
    laboratories,
    medicine_intakes,
    sibionics_routes,
    medical_cards,
    medical_card_data,
    fuel_station,
)
from cor_pass.config.config import settings
from cor_pass.services.ip2_location import initialize_ip2location
from loguru import logger
from cor_pass.services.auth import auth_service
from fastapi.responses import JSONResponse
from collections import defaultdict
from jose import JWTError, jwt

from cor_pass.services.websocket import check_session_timeouts, cleanup_auth_sessions, register_signature_expirer

from cor_pass.services.logger import setup_logging
from cor_pass.services.prometheus_multiprocess import setup_prometheus_multiprocess

setup_logging()
setup_prometheus_multiprocess()


all_licenses_info = [
    {
        "name": "IP2Location LITE Database License",
        "url": "https://lite.ip2location.com/",
        "description": "Используется для IP-геолокации. Требуется указание ссылки как часть условий лицензии.",
    },
    {
        "name": "OpenSlide (LGPL v2.1)",
        "url": "https://openslide.org/license/",
        "description": "Библиотека для чтения изображений с микроскопа. Распространяется под LGPL v2.1.",
    },
    {
        "name": "Psycopg (LGPL 3.0 / Modified BSD)",
        "url": "https://www.psycopg.org/docs/license.html",
        "description": "PostgreSQL адаптер для Python. Распространяется под двойной лицензией LGPL 3.0 или Modified BSD.",
    },
    {
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
        "description": "Многие компоненты API распространяются под разрешительной лицензией MIT.",
    },
    {
        "name": "Apache License 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0",
        "description": "Некоторые компоненты API распространяются под разрешительной лицензией Apache 2.0.",
    },
    {
        "name": "BSD 3-Clause License",
        "url": "https://opensource.org/licenses/BSD-3-Clause",
        "description": "Некоторые компоненты API распространяются под разрешительной лицензией BSD 3-Clause.",
    },
    {
        "name": "BSD 2-Clause License",
        "url": "https://opensource.org/licenses/BSD-2-Clause",
        "description": "Некоторые компоненты API распространяются под разрешительной лицензией BSD 2-Clause.",
    },
]

api_description = """
**COR-ID API** - это основной сервис идентификации и аутентификации пользователей в системе COR

---

### Используемые лицензии:
"""
for lic in all_licenses_info:
    api_description += f"- **{lic['name']}**: [Подробнее]({lic['url']})"
    if "description" in lic:
        api_description += f" - {lic['description']}"
    api_description += "\n"

api_description += """
---
*Все торговые марки являются собственностью их соответствующих владельцев.*
"""

app = FastAPI(
    title="COR-ID API",
    description=api_description,
    version="1.0.1",
    openapi_url="/openapi.json" if settings.app_env in ["development", "lab-neuro"] else None,
    docs_url="/docs" if settings.app_env in ["development", "lab-neuro"] else None,
    redoc_url="/redoc" if settings.app_env in ["development", "lab-neuro"] else None,
)

app.mount("/static", StaticFiles(directory="cor_pass/static"), name="static")

origins = settings.allowed_redirect_urls

# === Настройка Prometheus метрик с multiprocess поддержкой ===

# Создаем собственные метрики которые работают в multiprocess mode
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"]
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float("inf"))
)

# Кастомный middleware для сбора метрик
@app.middleware("http")
async def prometheus_metrics_middleware(request: Request, call_next):
    # Получаем route для endpoint (не path с параметрами)
    endpoint = request.url.path
    for route in app.routes:
        match = route.matches(request.scope)
        if match[0] == 2:  # Match.FULL
            endpoint = route.path
            break
    
    method = request.method
    
    # Засекаем время
    start_time = time.time()
    
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        status_code = 500
        raise
    finally:
        # Записываем метрики
        duration = time.time() - start_time
        HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
        HTTP_REQUEST_DURATION.labels(method=method, endpoint=endpoint, status_code=status_code).observe(duration)
    
    return response

# Endpoint для метрик с multiprocess поддержкой
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint с поддержкой multiprocess mode"""
    from prometheus_client import REGISTRY
    
    prom_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    
    # Если PROMETHEUS_MULTIPROC_DIR установлен - собираем метрики со всех workers
    if prom_dir:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        data = generate_latest(registry)
    else:
        # В single-process режиме используем дефолтный registry
        data = generate_latest(REGISTRY)
    
    # Если данных нет - возвращаем хотя бы дефолтный registry (для отладки)
    if not data or len(data) < 100:
        logger.warning(f"Metrics data is empty or too small: {len(data) if data else 0} bytes, falling back to REGISTRY")
        data = generate_latest(REGISTRY)
    
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)

# Дополнительные кастомные метрики
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


@app.exception_handler(ValueError)
async def validation_exception_handler(request: Request, exc: ValueError):
    return JSONResponse(
        # logger.error(f"Произошла ошибка валидации: {str(exc)}"),
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Произошла ошибка валидации", "error": str(exc)},
    )


# Маршруты
@app.get("/config")
def read_config():
    return {"ENV": settings.app_env}


@app.get("/", name="Корень")
def read_root(request: Request):
    REQUEST_COUNT.inc()
    with REQUEST_LATENCY.time():
        return FileResponse("cor_pass/static/COR_ID/login.html")


@app.get("/version")
async def get_version():
    return {"version": __version__}

@app.get("/api/healthchecker")
async def healthchecker(db: AsyncSession = Depends(get_db)):
    REQUEST_COUNT.inc()
    try:
        result = await db.execute(text("SELECT 1"))
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


app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)


# Middleware для добавления заголовка времени обработки
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["My-Process-Time"] = str(process_time)
    return response


# Middleware для фиксирования активных пользователей
@app.middleware("http")
async def track_active_users(request: Request, call_next):
    user_token = request.headers.get("Authorization")
    if user_token:
        token_parts = user_token.split(" ")
        if len(token_parts) >= 2:
            try:
                decoded_token = jwt.decode(
                    token_parts[1],
                    options={"verify_signature": False},
                    key=auth_service.SECRET_KEY,
                    algorithms=[auth_service.ALGORITHM],
                )
                oid = decoded_token.get("oid")
                await redis_client.set(oid, time.time())
            except JWTError:
                pass
    response = await call_next(request)
    return response


async def custom_identifier(request: Request) -> str:
    return request.client.host


# Событие при старте приложения
@app.on_event("startup")
async def startup():
    logger.info("------------- STARTUP --------------")
    await FastAPILimiter.init(redis_client, identifier=custom_identifier)
    asyncio.create_task(check_session_timeouts())
    asyncio.create_task(cleanup_auth_sessions())
    register_signature_expirer(app, async_session_maker)
    initialize_ip2location()
    await websocket_events_manager.init_redis_listener()
    if settings.app_env == "development":
        await create_modbus_client(app)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("------------- SHUTDOWN --------------")
    await close_modbus_client(app)


auth_attempts = defaultdict(list)
blocked_ips = {}

app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(records.router, prefix="/api")
app.include_router(password_generator.router, prefix="/api")
app.include_router(person.router, prefix="/api")
app.include_router(cor_id.router, prefix="/api")
app.include_router(otp_auth.router, prefix="/api")
app.include_router(lawyer.router, prefix="/api")
app.include_router(financier.router, prefix="/api")
app.include_router(doctor.router, prefix="/api")
app.include_router(cases.router, prefix="/api")
app.include_router(samples.router, prefix="/api")
app.include_router(cassettes.router, prefix="/api")
app.include_router(glasses.router, prefix="/api")
app.include_router(websocket.router, prefix="/api")
app.include_router(device_ws.router, prefix="/api")
app.include_router(device_proxy.router, prefix="/api")
app.include_router(dicom_router.router, prefix="/api")
app.include_router(svs_router.router, prefix="/api")
app.include_router(printing_device.router, prefix="/api")
app.include_router(printer.router, prefix="/api")
app.include_router(websocket_events.router, prefix="/api")
app.include_router(lab_assistants.router, prefix="/api")
app.include_router(cerbo_routes.router, prefix="/api")
app.include_router(energy_managers.router, prefix="/api")
app.include_router(blood_pressures.router, prefix="/api")
app.include_router(ecg_measurements.router, prefix="/api")
app.include_router(excel_router.router, prefix="/api")
app.include_router(scanner_router.router, prefix="/api")
app.include_router(medicines.router, prefix="/api")
app.include_router(first_aid_kits.router, prefix="/api")
app.include_router(support.router, prefix="/api")
app.include_router(ophthalmological_prescriptions.router, prefix="/api")
app.include_router(prescriptions.router, prefix="/api")
app.include_router(sibionics_routes.router, prefix="/api")
app.include_router(laboratories.router, prefix="/api")
app.include_router(medicine_intakes.router, prefix="/api")
app.include_router(medical_cards.router, prefix="/api")
app.include_router(medical_card_data.router, prefix="/api")
app.include_router(fuel_station.router, prefix="/api/fuel", tags=["Fuel Station"])

if __name__ == "__main__":
    uvicorn.run(
        app="main:app",
        host="192.168.153.203",
        port=8000,
        log_level="info",
        access_log=True,
        reload=settings.reload,
    )
# 192.168.153.203
