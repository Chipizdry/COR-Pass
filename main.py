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


from cor_pass.routes import auth
from cor_pass.database.db import get_db
from cor_pass.routes import auth, records, tags, password_generator, users, cor_id
from cor_pass.repository import users as repo_users
from cor_pass.config.config import settings
from cor_pass.services.logger import logger
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

app = FastAPI()
app.mount("/static", StaticFiles(directory="cor_pass/static"), name="static")

origins = [
    "http://192.168.153.203:8000" "http://localhost:3000",
    "http://192.168.153.21:3000",
]

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
    return FileResponse("cor_pass/static/login.html")
    # return "welcome"


@app.get("/api/healthchecker")
def healthchecker(db: Session = Depends(get_db)):
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


# Middleware для проверки подписи
@app.middleware("http")
async def verify_request_signature(request: Request, call_next):
    if settings.signing_key_verification:
        try:
            signature = request.headers.get("X-Signature")
            if signature is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature"
                )

            body = await request.body()
            body_str = body.decode()

            if not verify_signature(body_str, signature):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature"
                )

            return await call_next(request)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )
    else:
        return await call_next(request)


def verify_signature(body: str, signature: str) -> bool:
    computed_signature = hmac.new(
        settings.signing_key, body.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(
        computed_signature.encode("utf-8"), signature.encode("utf-8")
    )


# def create_signature(signing_key: str, body: str) -> str:
#     signature = hmac.new(settings.signing_key.encode(), body.encode(), hashlib.sha256).hexdigest()
#     return signature


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


# if settings.app_env == "production":
#     app.middleware("http")(verify_request_signature)


app.include_router(auth.router, prefix="/api")
app.include_router(records.router, prefix="/api")
app.include_router(tags.router, prefix="/api")
app.include_router(password_generator.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(cor_id.router, prefix="/api")


if __name__ == "__main__":
    uvicorn.run(
        app="main:app", host="192.168.153.203", port=8000, reload=settings.reload
    )
# 192.168.153.203
