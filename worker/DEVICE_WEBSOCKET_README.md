# Energetic Devices WebSocket Integration в Modbus Worker

## Обзор

Этот модуль предоставляет WebSocket подключение для энергетических устройств (Cerbo/Modbus) в контейнере `modbus_worker`.

**Поддерживаются только энергетические устройства** с аутентификацией email/password.

## Архитектура

```
┌─────────────────┐         ┌──────────────────┐
│  FastAPI (8000) │◄────────┤  Client/Frontend │
└────────┬────────┘         └──────────────────┘
         │ HTTP Proxy
         ▼
┌─────────────────────────────────┐
│   Modbus Worker (8003)          │
│                                 │
│  ┌──────────────────────────┐  │
│  │  WebSocket Server        │  │
│  │  - Energetic devices     │  │
│  │  - Email/Password auth   │  │
│  │  - Broadcast events      │  │
│  └──────────────────────────┘  │
└─────────────────────────────────┘
         ▲
         │ WebSocket
    ┌────┴────┐
    │ Cerbo   │
    │ Modbus  │
    └─────────┘
```

## Компоненты

### 1. WebSocket App (`worker/websocket_app.py`)
- FastAPI приложение для WebSocket подключений энергетических устройств
- Эндпоинты:
  
  **WebSocket:**
  - `WS /ws/devices?session_id={id}` - WebSocket с email/password аутентификацией
  
  **HTTP API:**
  - `POST /send_message` - Отправка сообщения на энергетическое устройство
  - `POST /broadcast_modbus_command` - Вручную отправить Modbus-команду всем устройствам
  - `GET /health` - Health check
  - `GET /devices/connected` - Список подключенных устройств
  - `GET /devices/{session_id}/status` - Статус конкретного устройства

### Background Tasks


### 2. Device Proxy (`cor_pass/routes/device_proxy.py`)
- HTTP API в главном FastAPI приложении (порт 8000)
- Проксирует запросы к WebSocket серверу в modbus_worker (порт 8003)
- Эндпоинты:
  - `POST /api/energetic_device_proxy/send_message` - Отправка сообщения устройству
  - `GET /api/energetic_device_proxy/devices/connected` - Список подключенных устройств
  - `GET /api/energetic_device_proxy/devices/{session_id}/status` - Статус устройства
  - `GET /api/energetic_device_proxy/health` - Проверка WebSocket сервера

## Использование

### Подключение энергетического устройства

Устройство (Cerbo/Modbus) подключается с аутентификацией:

```python
import websockets
import json
import asyncio

session_id = "unique_session_id"
uri = f"ws://localhost:8003/ws/devices?session_id={session_id}"

async with websockets.connect(uri) as websocket:
    # Первое сообщение - аутентификация
    auth_data = {
        "email": "user@example.com",
        "password": "password123"
    }
    await websocket.send(json.dumps(auth_data))
    
    # Ожидаем подтверждения
    response = await websocket.recv()
    auth_response = json.loads(response)
    
    if auth_response.get("status") == "authenticated":
        # Отправляем данные с устройства
        while True:
            device_data = {
                "battery_voltage": 24.5,
                "solar_power": 1500,
                "timestamp": "2025-10-27T12:00:00"
            }
            await websocket.send(json.dumps(device_data))
            await asyncio.sleep(2)
```

### Отправка сообщения на устройство

Через главное FastAPI приложение (рекомендуется):

```bash
# Через HTTP API proxy (рекомендуется)
curl -X POST "http://localhost:8000/api/energetic_device_proxy/send_message?session_token=unique_session_id" \
  -H "Authorization: Bearer {user_token}" \
  -H "Content-Type: application/json" \
  -d '{"command": "set_grid_feed", "power": 5000}'

# Напрямую к modbus_worker (только для отладки)
curl -X POST "http://localhost:8003/send_message" \
  -H "Content-Type: application/json" \
  -d '{
    "session_token": "unique_session_id",
    "data": {"command": "set_grid_feed", "power": 5000}
  }'
```

**Важно:** `session_token` должен совпадать с `session_id`, который был указан при подключении WebSocket:
```python
# При подключении
uri = f"ws://localhost:8003/ws/devices?session_id=unique_session_id"

# При отправке сообщения
session_token = "unique_session_id"  # Тот же ID!
```

### Получение списка подключенных устройств

```bash
# Через proxy API
curl "http://localhost:8000/api/energetic_device_proxy/devices/connected" \
  -H "Authorization: Bearer {user_token}"

# Напрямую
curl "http://localhost:8003/devices/connected"
```

### Проверка статуса устройства

```bash
# Через proxy API
curl "http://localhost:8000/api/energetic_device_proxy/devices/{session_id}/status" \
  -H "Authorization: Bearer {user_token}"

# Напрямую
curl "http://localhost:8003/devices/{session_id}/status"
```

### Ручная отправка Modbus-команды всем устройствам

```bash
# Отправить команду по умолчанию (09 03 00 00 00 0a c4 85)
curl -X POST "http://localhost:8003/broadcast_modbus_command"

# Отправить пользовательскую hex-команду
curl -X POST "http://localhost:8003/broadcast_modbus_command?hex_data=01%2003%2000%2000%2000%200a%20c5%2085"
```

Ответ:
```json
{
  "detail": "Modbus command broadcast complete",
  "total_devices": 3,
  "sent_successfully": 3,
  "failed": 0,
  "hex_command": "09 03 00 00 00 0a c4 85"
}
```

## Docker Compose

Modbus Worker контейнер настроен на порт 8001:

```yaml
modbus_worker:
  build:
    context: .
    dockerfile: Dockerfile.modbus_worker
  ports:
    - "8003:8003"
  environment:
    - APP_ENV=development
  depends_on:
    - postgres
    - redis
```

## Преимущества

1. **Изоляция**: WebSocket сервер отделен от основного API
2. **Масштабируемость**: modbus_worker можно масштабировать независимо
3. **Broadcast**: События рассылаются всем подключенным клиентам
4. **Надежность**: Использование Redis для управления соединениями
5. **Простота**: Устройства подключаются к одному эндпоинту

## Мониторинг

Health check WebSocket сервера:

```bash
curl "http://localhost:8003/health"
```

Ответ:
```json
{
  "status": "healthy",
  "service": "energetic_devices_websocket_server",
  "connected_devices": 5
}
```

## Разработка

### Локальный запуск

```bash
cd worker
python main_with_websocket.py
```

### Тестирование WebSocket

```python
import asyncio
import websockets
import json

async def test_energetic_device():
    session_id = "test_session_123"
    uri = f"ws://localhost:8003/ws/devices?session_id={session_id}"
    
    async with websockets.connect(uri) as ws:
        # Аутентификация
        auth = {"email": "test@example.com", "password": "password"}
        await ws.send(json.dumps(auth))
        
        # Получаем ответ
        response = await ws.recv()
        print(f"Auth response: {response}")
        
        # Отправляем данные
        data = {"test": "data"}
        await ws.send(json.dumps(data))

asyncio.run(test_energetic_device())
```

## Миграция

Старый эндпоинт в `cerbo_routes.py` можно оставить для обратной совместимости:

```python
# Старый: ws://localhost:8000/modbus/ws/devices
# Новый: ws://localhost:8003/ws/devices
```

## Troubleshooting

### Устройство не может подключиться

1. Проверьте, что modbus_worker запущен
2. Убедитесь, что порт 8003 открыт
3. Проверьте email/password credentials
4. Убедитесь, что указан корректный session_id в URL

### Сообщения не доходят до устройства

1. Проверьте, что устройство подключено:
   ```bash
   curl http://localhost:8003/devices/connected
   ```
2. Проверьте статус конкретной сессии:
   ```bash
   curl http://localhost:8003/devices/{session_id}/status
   ```
3. Убедитесь, что `session_token` в запросе совпадает с `session_id` при подключении
4. Проверьте Redis:
   ```bash
   # В контейнере Redis
   redis-cli GET ws:session:{session_id}
   # Должен вернуть connection_id
   ```
5. Посмотрите логи modbus_worker:
   ```bash
   docker-compose logs modbus_worker
   ```

### WebSocket разрывается

1. Проверьте сеть между клиентом и сервером
2. Проверьте логи на ошибки аутентификации
3. Увеличьте timeout в WebSocket клиенте
4. Проверьте, что credentials корректные

### Отладка подключения энергетического устройства

```python
import asyncio
import websockets
import json

async def debug_energetic_device():
    session_id = "test_session_123"
    uri = f"ws://localhost:8003/ws/devices?session_id={session_id}"
    
    print(f"Connecting to {uri}...")
    async with websockets.connect(uri) as ws:
        print("Connected! Sending auth...")
        
        # Аутентификация
        auth = {
            "email": "test@example.com",
            "password": "password"
        }
        await ws.send(json.dumps(auth))
        
        # Получаем ответ
        response = await ws.recv()
        print(f"Auth response: {response}")
        
        # Отправляем тестовые данные
        data = {"test": "data", "timestamp": "2025-10-27T12:00:00"}
        await ws.send(json.dumps(data))
        print(f"Sent data: {data}")
        
        # Ждем входящие сообщения
        while True:
            message = await ws.recv()
            print(f"Received: {message}")

asyncio.run(debug_energetic_device())
```
