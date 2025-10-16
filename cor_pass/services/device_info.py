from fastapi import Header, HTTPException, Request, status


def get_device_header(
    user_agent: str = Header(None, description="User-Agent header"),
    x_device_type: str = Header(None, description="X-Device-Type header"),
    x_device_os: str = Header(None, description="X-Device-OS header"),
    x_device_info: str = Header(None, description="X-Device-Info header"),
    x_app_id: str = Header(None, description="X-App-Id"),
    x_device_id: str = Header(None, description="X-Device-Id"),
) -> dict:
    """
    Получает информацию об устройстве из заголовков.
    """
    if not user_agent and not x_device_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required headers: User-Agent or X-Device-Type",
        )

    return {
        "device_type": x_device_type or "Desktop",  # Тип устройства
        "device_info": x_device_info or user_agent,  # Информация об устройстве
        "device_os": x_device_os or "Unknown OS",  # Операционная система
        "app_id": x_app_id, 
        "device_id": x_device_id
    }


def get_device_info(request: Request) -> dict:
    """
    Получает информацию об устройстве из запроса.
    Поддерживает как веб-браузеры, так и мобильные приложения.
    """
    user_agent = request.headers.get("User-Agent", "Unknown device")
    ip_address = get_client_ip(request)

    device_type = "Desktop"
    device_os = "Unknown OS"
    app_id = None
    device_id = None

    is_mobile_app = request.headers.get("X-Device-Type") is not None

    if is_mobile_app:
        device_type = request.headers.get("X-Device-Type", "Mobile")
        device_os = request.headers.get("X-Device-OS", "Unknown OS")
        device_info = request.headers.get("X-Device-Info", "Unknown device")
        app_id = request.headers.get("X-App-Id")  # уникальный id приложения
        device_id = request.headers.get("X-Device-Id")  # уникальный id устройства
    else:
        device_info = user_agent

        if "Mobile" in user_agent or "iPhone" in user_agent or "Android" in user_agent:
            device_type = "Mobile"

        if "Windows" in user_agent:
            device_os = "Windows"
        elif "Mac OS" in user_agent:
            device_os = "Mac OS"
        elif "iPhone" in user_agent:
            device_os = "iOS"
        elif "Android" in user_agent:
            device_os = "Android"
        elif "Linux" in user_agent:
            device_os = "Linux"

    return {
        "device_type": device_type,   # Тип устройства (Mobile, Desktop и т.д.)
        "device_info": device_info,   # Информация об устройстве
        "ip_address": ip_address,     # IP-адрес
        "device_os": device_os,       # Операционная система
        "app_id": app_id,             # Уникальный ID приложения (только для мобилок)
        "device_id": device_id,       # Уникальный ID устройства (только для мобилок)
    }


def get_client_ip(request: Request):
    """Получение реального IP-адреса клиента."""
    if "x-forwarded-for" in request.headers:
        client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
    elif "x-real-ip" in request.headers:
        client_ip = request.headers["x-real-ip"].strip()
    elif "http_client_ip" in request.headers:
        client_ip = request.headers["http_client_ip"].strip()
    else:
        client_ip = request.client.host
    return client_ip
