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

class RawTextPrintRequest(BaseModel):
    text: str = Field(..., min_length=1)
    printer_ip: str | None = None
    port: int = 9100
    timeout: int = 10
    encoding: str = "utf-8"
    newline: str = "\n"   # некоторые принтеры любят '\r\n'

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
        if protocol.upper() == "ZPL":
            cmd = f"^XA^FO50,50^A0N,40,40^FD{text}^FS^XZ"
        elif protocol.upper() == "EPL":
            cmd = f"N\nA50,50,0,4,1,1,N,\"{text}\"\nP1\n"
        elif protocol.upper() == "TSPL":
            cmd = f"SIZE 80 mm,40 mm\nCLS\nTEXT 100,100,\"3\",0,1,1,\"{text}\"\nPRINT 1\n"
        else:
            logger.error(f"Неизвестный протокол: {protocol}")
            return False

        return self.send(cmd.encode("utf-8"))


DEFAULT_RAW_PRINTER_IP = "192.168.154.98"  # IDPRT ID2X по сети

@router.post("/raw/print_text")
def print_text_raw(req: RawTextPrintRequest):
    host = req.printer_ip or DEFAULT_RAW_PRINTER_IP
    try:
        printer = EthernetPrinter9100(host, req.port, req.timeout)
        printer.print_text(req.text, encoding=req.encoding, newline=req.newline)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Raw print error to {host}:{req.port}: {e}")
        raise HTTPException(status_code=502, detail=f"Raw print failed: {e}")

def _tcp_connect(ip: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False

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
def print_with_protocol(data: dict):
    text = data.get("text", "")
    protocol = data.get("protocol", "ZPL")
    printer_ip = data.get("printer_ip", "192.168.154.98")

    printer = EthernetPrinter(printer_ip)
    success = printer.print_protocol(text, protocol)

    return {"status": "ok" if success else "error", "protocol": protocol}


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
