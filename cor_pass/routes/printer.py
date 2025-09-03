

import socket
import asyncio
import platform
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import httpx
from loguru import logger

# Единый роутер для всех принтеров
router = APIRouter(prefix="/printer", tags=["Printer"])

# =========================
# 1) RAW-печать по TCP:9100
# =========================

class ProtocolPrintRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Текст для печати")
    protocol: str = Field("ZPL", description="Протокол: ZPL | EPL | TSPL")
    printer_ip: str = Field(..., description="IP-адрес принтера")
    port: int = Field(9100, description="TCP порт (по умолчанию 9100)")
    timeout: int = Field(10, description="Таймаут соединения в секундах")

class EthernetPrinter9100:
    def __init__(self, host: str, port: int = 9100, timeout: int = 10):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send_bytes(self, data: bytes) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(self.timeout)
            sock.connect((self.host, self.port))
            sock.sendall(data)

    def print_text(self, text: str, *, encoding: str = "utf-8", newline: str = "\n") -> None:
        payload = text.encode(encoding) + newline.encode(encoding)
        self.send_bytes(payload)



class EthernetPrinter:
    def __init__(self, host: str, port: int = 9100, timeout: int = 10):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send(self, data: bytes) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))
                sock.sendall(data)
            return True
        except Exception as e:
            logger.error(f"Ошибка печати на {self.host}:{self.port} → {e}")
            return False

    def print_protocol(self, text: str, protocol: str = "ZPL") -> bool:
        protocol = protocol.upper()
        if protocol == "ZPL":
            cmd = f"^XA^FO50,50^A0N,40,40^FD{text}^FS^XZ"
        elif protocol == "EPL":
            cmd = f"N\r\nA50,50,0,4,1,1,N,\"{text}\"\r\nP1\r\n"
        elif protocol == "TSPL":
            cmd = f"SIZE 80 mm,40 mm\r\nCLS\r\nTEXT 100,100,\"3\",0,1,1,\"{text}\"\r\nPRINT 1\r\n"
        else:
            logger.error(f"Неизвестный протокол: {protocol}")
            return False

        return self.send(cmd.encode("utf-8"))




DEFAULT_RAW_PRINTER_IP = "192.168.154.98"  # IDPRT ID2X по сети



@router.get("/raw/check")
async def check_raw_printer(
    ip: str = Query(..., description="IP-адрес RAW-принтера (TCP:9100)"),
    port: int = 9100,
    timeout: float = 1.5,
):
    loop = asyncio.get_event_loop()
    ok = await loop.run_in_executor(None, _tcp_connect, ip, port, timeout)
    return {"available": ok}



@router.post("/print_protocol")
def print_with_protocol(req: ProtocolPrintRequest):
    printer = EthernetPrinter(req.printer_ip, req.port, req.timeout)
    success = printer.print_protocol(req.text, req.protocol)

    return {
        "status": "ok" if success else "error",
        "protocol": req.protocol,
        "printer_ip": req.printer_ip,
    }


# =======================================
# 2) Существующие HTTP-принтеры (порт 8080)
# =======================================

class LabelData(BaseModel):
    number_model_id: int
    content: str
    uuid: str

class LabelBatchRequest(BaseModel):
    printer_ip: str
    labels: list[LabelData]

@router.post("/print_labels")
async def print_labels(data: LabelBatchRequest):
    printer_url = f"http://{data.printer_ip}:8080/task/new"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                printer_url, json={"labels": [label.dict() for label in data.labels]}
            )
        if response.status_code == 200:
            return {"success": True, "printer_response": response.text}
        raise HTTPException(status_code=502, detail=f"Printer error: {response.text}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send to printer: {str(e)}")

@router.get("/check_printer")
async def check_printer(ip: str = Query(..., description="IP-адрес принтера")):
    url = f"http://{ip}:8080/task"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(url)
            return {"available": response.status_code == 200}
    except Exception:
        return {"available": False}

@router.get("/ping")
async def ping_printer(ip: str = Query(..., description="IP-адрес принтера")):
    try:
        param = "-n" if platform.system().lower() == "windows" else "-c"
        command = ["ping", param, "1", "-w", "1000", ip]
        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        return {"reachable": process.returncode == 0}
    except Exception as e:
        logger.error(f"[ping_printer] Ошибка выполнения ping: {e}")
        return {"reachable": False}