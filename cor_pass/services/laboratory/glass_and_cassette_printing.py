from typing import List

from fastapi import HTTPException, Request, status
import httpx
from loguru import logger

from cor_pass.schemas import PrintLabel


PRINTER_BASE_URL = "http://{printer_ip}:8080/task/new"

async def print_labels(printer_ip: str, labels_to_print: List[PrintLabel], request: Request):
    """
    Отправляет запрос на печать меток на принтер.

    """
    logger.debug(request.base_url)
    if request.base_url == "http://dev-corid.cor-medical.ua/":
        logger.debug("Тестовая печать успешна")
        return {"success": True, "printer_response": "Делаем вид что принтер напечатал"}
    printer_url = PRINTER_BASE_URL.format(printer_ip=printer_ip)
    try:
        async with httpx.AsyncClient() as client:
            labels_data = [label.dict() for label in labels_to_print]
            
            logger.debug(f"Отправка на принтер {printer_url}: {labels_data}") 

            response = await client.post(
                printer_url,
                json={"labels": labels_data},
                timeout=10
            )
            response.raise_for_status()

            logger.debug(f"Статус ответа принтера: {response.status_code}, тело: {response.text}")
            return {"success": True, "printer_response": response.text}

    except httpx.HTTPStatusError as e:
        logger.error(f"Произошла HTTP ошибка: {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Принтер ответил ошибкой: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"Произошла ошибка запроса: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Не удалось подключиться к принтеру по адресу {printer_ip}: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Произошла непредвиденная ошибка: {e}")
        raise HTTPException(
            status_code=503, detail=f"Не удалось отправить на принтер: {str(e)}"
        )