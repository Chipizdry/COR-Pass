from fastapi import Header, HTTPException, Request, status


def get_device_header(
    user_agent: str = Header(None, description="User-Agent header"),
    x_device_type: str = Header(None, description="X-Device-Type header"),
    x_device_os: str = Header(None, description="X-Device-OS header"),
    x_device_info: str = Header(None, description="X-Device-Info header"),
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
    }


def get_device_info(request: Request) -> dict:
    """
    Получает информацию об устройстве из запроса.
    Поддерживает как веб-браузеры, так и мобильные приложения.
    """
    user_agent = request.headers.get("User-Agent", "Unknown device")
    ip_address = request.client.host

    # Определяем тип устройства и ОС
    device_type = "Desktop"  # По умолчанию считаем устройство десктопом
    device_os = "Unknown OS"

    # Проверяем, является ли запрос от мобильного приложения
    is_mobile_app = request.headers.get("X-Device-Type") is not None

    if is_mobile_app:
        # Если запрос от мобильного приложения, используем кастомные заголовки
        device_type = request.headers.get("X-Device-Type", "Mobile")
        device_os = request.headers.get("X-Device-OS", "Unknown OS")
        device_info = request.headers.get("X-Device-Info", "Unknown device")
    else:
        # Если запрос от веб-браузера, анализируем User-Agent
        device_info = user_agent

        # Определяем тип устройства
        if "Mobile" in user_agent or "iPhone" in user_agent or "Android" in user_agent:
            device_type = "Mobile"

        # Определяем операционную систему
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
        "device_type": device_type,  # Тип устройства (Mobile, Desktop и т.д.)
        "device_info": device_info,  # Информация об устройстве
        "ip_address": ip_address,  # IP-адрес
        "device_os": device_os,  # Операционная система
    }
