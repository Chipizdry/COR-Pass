import asyncio
import platform
from fastapi import APIRouter, HTTPException, Query
import httpx
from pydantic import BaseModel
from loguru import logger
from cor_pass.schemas import PrintRequest


router = APIRouter(tags=["Printer"])


PRINTER_IP = "192.168.154.209"


class LabelData(BaseModel):
    number_model_id: int
    content: str
    uuid: str


class PrintRequest(BaseModel):
    printer_ip: str
    labels: list[LabelData]


@router.post("/print_labels")
async def print_labels(data: PrintRequest):
    printer_url = f"http://{data.printer_ip}:8080/task/new"
    try:
        async with httpx.AsyncClient() as client:
            # Отправляем только данные меток без IP
            response = await client.post(
                printer_url, json={"labels": [label.dict() for label in data.labels]}
            )
            if response.status_code == 200:
                return {"success": True, "printer_response": response.text}
            else:
                raise HTTPException(
                    status_code=502, detail=f"Printer error: {response.text}"
                )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to send to printer: {str(e)}"
        )


@router.get("/check_printer")
async def check_printer(ip: str = Query(..., description="IP-адрес принтера")):
    url = f"http://{ip}:8080/task"
    # logger.info(f"[check_printer] Проверка доступности по URL: {url}")

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(url)
            # logger.info(f"[check_printer] Код ответа от принтера: {response.status_code}")
            return {"available": response.status_code == 200}
    except Exception as e:
        # logger.error(f"[check_printer] Ошибка запроса к принтеру: {e}")
        return {"available": False}


async def ping_printer(printer_ip: str):
    try:
        param = "-n" if platform.system().lower() == "windows" else "-c"
        command = ["ping", param, "1", "-w", "1000", printer_ip]

        # logger.info(f"[ping_printer] Выполняется команда: {' '.join(command)}")

        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        # logger.info(f"[ping_printer] STDOUT: {stdout.decode()}")
        # logger.info(f"[ping_printer] STDERR: {stderr.decode()}")
        # logger.info(f"[ping_printer] Код возврата: {process.returncode}")

        return process.returncode == 0
    except Exception as e:
        logger.error(f"[ping_printer] Ошибка выполнения ping: {e}")
        return False
