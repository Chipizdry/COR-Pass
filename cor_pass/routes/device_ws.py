import json
from typing import List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse



router = APIRouter(prefix="/device_ws", tags=["Device WebSockets"])


active_device_connections: dict[str, WebSocket] = {}
device_data: dict[str, dict] = {}  

@router.websocket("/connect/{device_id}")
async def device_websocket_endpoint(websocket: WebSocket, device_id: str):

    # Тут можно добавить проверку наличия ID устройства в нашей базе данных и в зависимости от этого разрешать / отклонять соединение 

    await websocket.accept()
    print(f"Устройство {device_id} подключилось.")
    active_device_connections[device_id] = websocket
    try:
        while True:        
            data = await websocket.receive_text()
            print(f"Получены данные от устройства {device_id}: {data}")
            try:
                json_data = json.loads(data)
                device_data[device_id] = json_data  # Сохраняем последние полученные данные, к примеру
            except json.JSONDecodeError:
                print(f"Получены некорректные JSON данные от устройства {device_id}: {data}")
    except WebSocketDisconnect:
        print(f"Устройство {device_id} отключилось.")
    except Exception as e:
        print(f"Ошибка в WebSocket-соединении с устройством {device_id}: {e}")
    finally:
        if device_id in active_device_connections:
            del active_device_connections[device_id]
        if device_id in device_data:
            del device_data[device_id]


@router.post("/send_command/{device_id}")
async def send_command_to_device(device_id: str, command: dict):
    """
    Отправляет команду указанному устройству через WebSocket.
    """
    if device_id in active_device_connections:
        websocket = active_device_connections[device_id]
        try:
            await websocket.send_json(command)
            return {"status": "command_sent", "device_id": device_id, "command": command}
        except Exception as e:
            return {"status": "error_sending", "device_id": device_id, "error": str(e)}
    else:
        return {"status": "device_not_connected", "device_id": device_id}


@router.get("/connected_devices", response_model=List[str])
async def get_connected_devices():
    """
    Возвращает список всех подключенных устройств.
    """
    return list(active_device_connections.keys())



@router.get("/device_data/{device_id}", response_model=Optional[dict])
async def get_device_data(device_id: str):
    """
    Возвращает последние полученные данные от указанного устройства.
    """
    if device_id in device_data:
        return device_data[device_id]
    return JSONResponse(status_code=404, content={"message": f"Данные для устройства с ID {device_id} не найдены."})


@router.post("/disconnect/{device_id}")
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
    return JSONResponse(status_code=404, content={"message": f"Устройство с ID {device_id} не подключено."})