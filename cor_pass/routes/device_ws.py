import json
from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    status,
)
from fastapi.responses import JSONResponse
from cor_pass.database.models import AccessLevel, Device, DeviceStatus, User
from cor_pass.services.access import user_access
from cor_pass.repository import device as repository_devices
from cor_pass.repository import person as repository_users
from cor_pass.schemas import (
    DeviceAccessResponse,
    DeviceResponse,
    DeviceRegistration,
    GrantDeviceAccess,
)
from cor_pass.services.auth import auth_service
from cor_pass.database.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from cor_pass.services.access import admin_access

router = APIRouter(prefix="/device_ws", tags=["Device WebSockets"])


active_device_connections: dict[str, WebSocket] = {}
device_data: dict[str, dict] = {}


@router.websocket("/connect/{token}")
async def device_websocket_endpoint(
    websocket: WebSocket, token: str, db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint для подключения устройств с аутентификацией по JWT.
    """
    print(token)
    await websocket.accept()
    try:
        device = await auth_service.get_current_device(token, db)
        device_id_str = str(
            device.id
        )  # Преобразуем ID устройства в строку для ключей словарей
        # device_id_str = "str(device.id)"
        # await websocket.accept()
        print(f"Устройство с ID {device_id_str} (токен: {token[:10]}...) подключилось.")
        active_device_connections[device_id_str] = websocket
        try:
            while True:
                data = await websocket.receive_text()
                print(f"Получены данные от устройства {device_id_str}: {data}")
                try:
                    json_data = json.loads(data)
                    device_data[device_id_str] = (
                        json_data  # Сохраняем последние полученные данные, к примеру
                    )
                    # Тут можно добавить логику обработки полученных данных от устройства
                    # Например, сохранение в базу данных через сессию db
                except json.JSONDecodeError:
                    print(
                        f"Получены некорректные JSON данные от устройства {device_id_str}: {data}"
                    )
        except WebSocketDisconnect:
            print(f"Устройство {device_id_str} отключилось.")
        except Exception as e:
            print(f"Ошибка в WebSocket-соединении с устройством {device_id_str}: {e}")
        finally:
            if device_id_str in active_device_connections:
                del active_device_connections[device_id_str]
            if device_id_str in device_data:
                del device_data[device_id_str]
    except HTTPException as e:
        print(f"Ошибка аутентификации устройства: {e.detail}")
        await websocket.close(code=e.status_code, reason=e.detail)
    except Exception as e:
        print(f"Непредвиденная ошибка при подключении устройства: {e}")
        await websocket.close(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR, reason="Internal Server Error"
        )


@router.post("/send_command/{device_id}", dependencies=[Depends(user_access)])
async def send_command_to_device(device_id: str, command: dict):
    """
    Отправляет команду указанному устройству через WebSocket.
    """
    if device_id in active_device_connections:
        websocket = active_device_connections[device_id]
        try:
            await websocket.send_json(command)
            return {
                "status": "command_sent",
                "device_id": device_id,
                "command": command,
            }
        except Exception as e:
            return {"status": "error_sending", "device_id": device_id, "error": str(e)}
    else:
        return {"status": "device_not_connected", "device_id": device_id}


@router.get(
    "/connected_devices", dependencies=[Depends(user_access)], response_model=List[str]
)
async def get_connected_devices():
    """
    Возвращает список всех подключенных устройств.
    """
    return list(active_device_connections.keys())


@router.get(
    "/device_data/{device_id}",
    dependencies=[Depends(user_access)],
    response_model=Optional[dict],
)
async def get_device_data(device_id: str):
    """
    Возвращает последние полученные данные от указанного устройства.
    """
    if device_id in device_data:
        return device_data[device_id]
    return JSONResponse(
        status_code=404,
        content={"message": f"Данные для устройства с ID {device_id} не найдены."},
    )


@router.post("/disconnect/{device_id}", dependencies=[Depends(user_access)])
async def disconnect_device(device_id: str):
    """
    Закрывает WebSocket-соединение с указанным устройством.
    """
    if device_id in active_device_connections:
        websocket = active_device_connections[device_id]
        await websocket.close()
        del active_device_connections[device_id]
        if device_id in device_data:
            del device_data[device_id]
        return {"status": "disconnected", "device_id": device_id}
    return JSONResponse(
        status_code=404,
        content={"message": f"Устройство с ID {device_id} не подключено."},
    )


# Активация нового устройства по его токену
@router.post(
    "/activate", response_model=DeviceResponse, dependencies=[Depends(user_access)]
)
async def activate_device(
    registration: DeviceRegistration,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    manufactured_device = await repository_devices.get_manufactured_device_by_token(
        db, registration.device_token
    )
    if not manufactured_device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Устройство не найдено или уже активировано",
        )
    jwt_token = await auth_service.create_device_jwt(
        device_id=manufactured_device.id, user_id=current_user.cor_id, expires_delta=10
    )
    db_device = await repository_devices.create_device(
        db,
        id=manufactured_device.id,
        token=jwt_token,
        name=f"Device-{manufactured_device.serial_number}",
        user_id=current_user.cor_id,
        serial_number=manufactured_device.serial_number,
    )
    await repository_devices.update_manufactured_device_status(
        db, manufactured_device, DeviceStatus.ACTIVATED
    )

    return DeviceResponse(
        token=db_device.token, device_name=db_device.name, user_id=db_device.user_id
    )


router.websocket("/ws")


async def websocket_endpoint(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    await websocket.accept()
    try:
        initial_data = await websocket.receive_json()
        token: str = initial_data.get("token")
        if not token:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Токен отсутствует"
            )
            return

        device = await auth_service.get_current_device(token, db)
        if not device:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Неверный токен"
            )
            return

        await websocket.send_text(
            f"Успешная аутентификация устройства (ID: {device.id}, Name: {device.name})"
        )

        while True:
            data = await websocket.receive_text()
            await websocket.send_text(
                f"Сообщение от устройства (ID: {device.id}, Name: {device.name}) получено: {data}"
            )

    except WebSocketDisconnect:
        print(f"WebSocket соединение с устройством разорвано")
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=str(e))


@router.post("/devices/{device_id}/share", response_model=DeviceAccessResponse)
async def share_device(
    access_data: GrantDeviceAccess,
    current_user: User = Depends(auth_service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    device = await repository_devices.get_device_by_id(
        device_id=access_data.device_id, db=db
    )
    if device:
        if device.user_id != current_user.cor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Вы не являетесь владельцем этого устройства",
            )

    user_to_grant_access = await repository_users.get_user_by_corid(
        db=db, cor_id=access_data.user_id
    )
    if not user_to_grant_access:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь для предоставления доступа не найден",
        )

    existing_access = await repository_devices.get_device_access(
        db=db,
        device_id=access_data.device_id,
        granting_user_id=current_user.cor_id,
        accessing_user_id=access_data.user_id,
    )

    if existing_access:
        updated_access = await repository_devices.update_device_access(
            db, existing_access, access_data.access_level
        )
        return updated_access
    else:
        new_access = await repository_devices.create_device_access(
            db,
            access_data.device_id,
            current_user.cor_id,
            access_data.user_id,
            access_data.access_level,
        )
        return new_access


@router.get("/devices/{device_id}/data", dependencies=[Depends(user_access)])
async def get_device_data(
    device: Device = Depends(
        lambda device_id, current_user, db: auth_service.verify_device_access(
            device_id=device_id,
            current_user_id=current_user.cor_id,
            db=db,
            required_level=AccessLevel.READ,
        )
    ),
    db: AsyncSession = Depends(get_db),
):
    # Здесь будет логика получения данных с устройства
    return {"device_id": device.id, "data": "some sensor data"}


@router.post("/devices/{device_id}/command", dependencies=[Depends(user_access)])
async def send_command_to_device(
    device: Device = Depends(
        lambda device_id, current_user, db: auth_service.verify_device_access(
            device_id=device_id,
            current_user_id=current_user.cor_id,
            db=db,
            required_level=AccessLevel.READ_WRITE,
        )
    ),
    db: AsyncSession = Depends(get_db),
    command: str = "start",
):
    # Здесь будет логика отправки команды на устройство
    return {"device_id": device.id, "command_sent": command}


@router.post("/manufactured_devices", dependencies=[Depends(admin_access)])
async def generate_new_manufactured_devices(
    generation_number: int, db: AsyncSession = Depends(get_db)
):
    created_devices = await repository_devices.create_manufactured_devices_bulk(
        db=db, count=generation_number
    )
    devices_tokens = []
    for dev in created_devices:
        devices_tokens.append(f"device {dev.serial_number} - token {dev.token}")
    return {"message": f"{devices_tokens}"}
