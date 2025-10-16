import socket
import asyncio
import platform
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import httpx
from loguru import logger
from typing import Optional, Dict, Any
# Единый роутер для всех принтеров
router = APIRouter(prefix="/printer", tags=["Printer"])

# =========================
# 1) RAW-печать по TCP:9100
# =========================

class CodePrintRequest(BaseModel):
    data: str = Field(..., description="Данные для QR или штрих-кода")
    protocol: str = Field("ZPL", description="Протокол: ZPL | EPL | TSPL")
    printer_ip: str = Field(..., description="IP-адрес принтера")
    port: int = Field(9100, description="TCP порт")
    timeout: int = Field(10, description="Таймаут соединения")


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

class EthernetPrinter(EthernetPrinter):  # расширяем существующий класс
    def print_barcode(self, data: str, protocol: str = "ZPL") -> bool:
        """
        Печать штрих-кода или QR-кода.
        :param data: строка с данными для кода
        :param protocol: ZPL | EPL | TSPL
        """
        protocol = protocol.upper()
        if protocol == "ZPL":
            # Пример печати QR-кода и Code128 в ZPL
            # QR-код
            cmd = f"^XA^FO50,50^BQN,2,5^FDLA,{data}^FS^XZ"
            # Для штрих-кода Code128 можно использовать:
            # cmd = f"^XA^FO50,50^BCN,100,Y,N,N^FD{data}^FS^XZ"
        elif protocol == "EPL":
            # EPL поддерживает только Code128 / Code39
            # Пример Code128
            cmd = f"N\r\nB50,50,0,1,2,50,100,\"{data}\"\r\nP1\r\n"
        elif protocol == "TSPL":
            # TSPL печатает QR-код и Code128
            # QR-код
            cmd = f"SIZE 80 mm,40 mm\r\nCLS\r\nQRCODE 100,100,L,5,A,0,\"{data}\"\r\nPRINT 1\r\n"
            # Для Code128:
            # cmd = f"SIZE 80 mm,40 mm\r\nCLS\r\nBARCODE 50,50,\"128\",100,1,0,2,2,\"{data}\"\r\nPRINT 1\r\n"
        else:
            logger.error(f"Неизвестный протокол для печати кода: {protocol}")
            return False

        return self.send(cmd.encode("utf-8"))



def _tcp_connect(ip, port=9100, timeout=1.5):
    try:
        with socket.create_connection((ip, port), timeout):
            return True
    except:
        return False



def get_pjl_info(ip, port=9100, timeout=1.5):
    try:
        with socket.create_connection((ip, port), timeout) as s:
            # Сначала reset
            s.send(b"\x1b%-12345X\r\n")
            # Потом запрос информации
            s.send(b"@PJL INFO ID\r\n")
            s.send(b"\x1b%-12345X\r\n")  # закрытие PJL-сессии
            data = s.recv(1024)
            return data.decode(errors="ignore").strip()
    except Exception:
        return None

def decode_printer_status(byte: int) -> dict:
    return {
        "not_busy": not (byte & 0b00000001),   # 0 = занят, 1 = готов
        "online": not (byte & 0b00000100),     # 0 = оффлайн, 1 = онлайн
    }

def decode_offline_status(byte: int) -> dict:
    return {
        "cover_open": bool(byte & 0b00000100),
        "paper_feed_button_pressed": bool(byte & 0b00001000),
        "error_present": bool(byte & 0b00100000),
    }

def decode_error_status(byte: int) -> dict:
    return {
        "cutter_error": bool(byte & 0b00000100),
        "unrecoverable_error": bool(byte & 0b00100000),
        "auto_recoverable_error": bool(byte & 0b01000000),
    }

def decode_paper_status(byte: int) -> dict:
    return {
        "paper_near_end": bool(byte & 0b00000001),
        "paper_end": bool(byte & 0b00000100),
    }


def get_escpos_status(ip: str, port: int = 9100, timeout: float = 1.5):
    """
    Запрос статуса ESC/POS через DLE EOT.
    Возвращает словарь со статусами.
    """
    commands = {
        "printer_status": (b"\x10\x04\x01", decode_printer_status),
        "offline_status": (b"\x10\x04\x02", decode_offline_status),
        "error_status":   (b"\x10\x04\x03", decode_error_status),
        "paper_status":   (b"\x10\x04\x04", decode_paper_status),
    }
    status_result = {}

    try:
        with socket.create_connection((ip, port), timeout) as s:
            for name, (cmd, decoder) in commands.items():
                s.sendall(cmd)
                data = s.recv(1)
                if data:
                    byte = data[0]
                    status_result[name] = {
                        "raw": format(byte, "08b"),  # для отладки
                        "decoded": decoder(byte),    # уже в человекочитаемом виде
                    }
                else:
                    status_result[name] = {"raw": None, "decoded": None}
    except Exception as e:
        return {"error": str(e)}

    return status_result

def detect_printer_type(ip: str, port: int = 9100, timeout: float = 2.0) -> Dict[str, Any]:
    """
    Определяет тип принтера по ответам на различные команды
    """
    result = {
        "printer_ip": ip,
        "port": port,
        "is_printer": False,
        "printer_type": "unknown",
        "details": {},
        "raw_responses": {}
    }
    
    def send_command(command: bytes, description: str) -> Optional[str]:
        try:
            with socket.create_connection((ip, port), timeout) as s:
                s.sendall(command)
                s.settimeout(timeout)
                response = s.recv(4096)
                return response.decode(errors="ignore").strip()
        except Exception as e:
            logger.debug(f"Ошибка при отправке команды {description}: {e}")
            return None
    
    # Команды для определения типа принтера
    commands = {
        "ZPL_PJL_ID": (b"\x1b%-12345X@PJL INFO ID\r\n\x1b%-12345X", "ZPL PJL INFO ID"),
        "ZPL_PJL_STATUS": (b"\x1b%-12345X@PJL INFO STATUS\r\n\x1b%-12345X", "ZPL PJL STATUS"),
        "EPL_HS": (b"~HS\r\n", "EPL ~HS"),
        "TSPL_STATUS": (b"! U1 get status\r\n", "TSPL get status"),
        "ESC_POS_STATUS": (b"\x10\x04\x01", "ESC/POS status"),
        "RAW_TEST": (b"TEST\r\n", "Raw test"),
    }
    
    # Отправляем все команды и собираем ответы
    for key, (cmd, desc) in commands.items():
        response = send_command(cmd, desc)
        result["raw_responses"][key] = response
        
        # Анализируем ответы для определения типа принтера
        if response:
            # ZPL принтеры обычно отвечают на PJL команды
            if "PJL" in key and ("READY" in response or "ZEBRA" in response.upper() or "ZPL" in response.upper()):
                result["is_printer"] = True
                result["printer_type"] = "ZPL"
                result["details"]["model"] = response
                
            # EPL принтеры отвечают на ~HS
            elif key == "EPL_HS" and any(x in response for x in [",", "ONLINE", "OFFLINE", "PAPER"]):
                result["is_printer"] = True
                result["printer_type"] = "EPL"
                result["details"]["status"] = response
                
            # TSPL принтеры
            elif key == "TSPL_STATUS" and any(x in response for x in ["READY", "PAPER", "HEAD"]
):
                result["is_printer"] = True
                result["printer_type"] = "TSPL"
                result["details"]["status"] = response
                
            # ESC/POS принтеры
            elif key == "ESC_POS_STATUS" and len(response) >= 1:
                result["is_printer"] = True
                result["printer_type"] = "ESC/POS"
                result["details"]["status_byte"] = format(ord(response[0]), "08b")
    
    # Если не определили по специфическим командам, проверяем общую доступность
    if not result["is_printer"]:
        # Проверяем, открыт ли порт вообще
        if _tcp_connect(ip, port, timeout):
            result["is_printer"] = True  # Предполагаем, что это принтер, если порт открыт
            result["printer_type"] = "Generic_RAW"
            result["details"]["note"] = "Port is open but printer type could not be determined"
    
    return result

@router.get("/verify_printer")
async def verify_printer(
    ip: str = Query(..., description="IP-адрес принтера"),
    port: int = Query(9100, description="TCP порт принтера"),
    timeout: float = Query(2.0, description="Таймаут соединения")
):
    """
    Проверяет, что по указанному IP и порту действительно находится принтер
    и определяет его тип.
    """
    loop = asyncio.get_event_loop()
    
    # Проверяем доступность порта
    is_available = await loop.run_in_executor(None, _tcp_connect, ip, port, timeout)
    
    if not is_available:
        return {
            "available": False,
            "is_printer": False,
            "printer_type": "unknown",
            "details": {"error": "Port is not accessible"}
        }
    
    # Определяем тип принтера
    printer_info = await loop.run_in_executor(None, detect_printer_type, ip, port, timeout)
    
    return {
        "available": True,
        "is_printer": printer_info["is_printer"],
        "printer_type": printer_info["printer_type"],
        "details": printer_info["details"],
        "raw_responses": printer_info.get("raw_responses", {})
    }

@router.get("/raw/check")
async def check_raw_printer(ip: str = Query(...), port: int = 9100, timeout: float = 1.5):
    loop = asyncio.get_event_loop()
    available = await loop.run_in_executor(None, _tcp_connect, ip, port, timeout)
    info = await loop.run_in_executor(None, get_pjl_info, ip, port, timeout) if available else None
    return {"available": available, "info": info}

    

@router.get("/raw/universal_status")
async def check_universal_status(ip: str = Query(..., description="IP принтера"),
                                 port: int = 9100,
                                 timeout: float = 2.0):
    """
    Асинхронный универсальный опрос принтера:
    - ZPL через PJL INFO STATUS
    - EPL через ~HS
    - TSPL через ! U1 get status
    Возвращает словарь со статусами по каждому протоколу.
    """
    loop = asyncio.get_running_loop()

    def send_tcp_command(cmd: bytes) -> str:
        """Вложенная синхронная функция для отправки TCP-команды с таймаутом."""
        try:
            with socket.create_connection((ip, port), timeout=timeout) as s:
                s.sendall(cmd)
                s.settimeout(timeout)
                chunks = []
                while True:
                    try:
                        data = s.recv(4096)
                        if not data:
                            break
                        chunks.append(data)
                    except socket.timeout:
                        break
                if chunks:
                    return b"".join(chunks).decode(errors="ignore").strip()
                return "Нет ответа"
        except Exception as e:
            return f"Ошибка: {e}"

    def poll_printer() -> dict:
        results = {}

        # ZPL через PJL INFO STATUS
        results['ZPL'] = {}
        zpl_pjl_cmds = {
            "~HS": b"\x1b%-12345X@PJL INFO STATUS\r\n\x1b%-12345X",
            "~HQES": b"\x1b%-12345X@PJL INFO STATUS\r\n\x1b%-12345X",
            "~HQ": b"\x1b%-12345X@PJL INFO STATUS\r\n\x1b%-12345X"
        }
        for cmd_name, cmd_bytes in zpl_pjl_cmds.items():
            results['ZPL'][cmd_name] = send_tcp_command(cmd_bytes)

        # EPL ~HS
        results['EPL'] = {}
        results['EPL']['~HS'] = send_tcp_command(b"~HS\r\n")

        # TSPL ! U1 get status
        results['TSPL'] = {}
        results['TSPL']['! U1 get status'] = send_tcp_command(b"! U1 get status\r\n")

        return results

    # Асинхронно запускаем синхронный опрос через ThreadPoolExecutor
    status = await loop.run_in_executor(None, poll_printer)
    return status





@router.post("/print_protocol")
def print_with_protocol(req: ProtocolPrintRequest):
    printer = EthernetPrinter(req.printer_ip, req.port, req.timeout)
    success = printer.print_protocol(req.text, req.protocol)

    return {
        "status": "ok" if success else "error",
        "protocol": req.protocol,
        "printer_ip": req.printer_ip,
    }




@router.post("/print_code")
def print_code(req: CodePrintRequest):
    printer = EthernetPrinter(req.printer_ip, req.port, req.timeout)
    success = printer.print_barcode(req.data, req.protocol)
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