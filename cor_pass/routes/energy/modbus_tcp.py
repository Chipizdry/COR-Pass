


import socket
import struct
from threading import Lock
from fastapi import APIRouter
from typing import List


router = APIRouter(prefix="/modbus_tcp", tags=["Modbus TCP"])
# ------------------------ CRC16 ------------------------
def modbus_crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if (crc & 1) else crc >> 1
    return crc

# ------------------------ ModbusTCP ------------------------
class ModbusTCP:
    def __init__(self, host: str, port: int = 502, slave_id: int = 1, timeout: int = 3):
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.sock = None
        self.lock = Lock()

    def connect(self):
        self.close()
        try:
            s = socket.create_connection((self.host, self.port), timeout=self.timeout)
            s.settimeout(self.timeout)
            self.sock = s
            return True
        except Exception as e:
            print(f"✗ Ошибка подключения: {e}")
            return False

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None

    def read(self, start: int, count: int, func: int = 3):
        with self.lock:
            if not self.sock and not self.connect():
                return None

            frame = struct.pack(">B B H H", self.slave_id, func, start, count)
            crc = modbus_crc16(frame)
            frame += struct.pack("<H", crc)

            try:
                self.sock.sendall(frame)
                response = self.sock.recv(256)
            except Exception:
                self.connect()
                return None

            if not response:
                self.connect()
                return None

            # Проверка CRC
            data = response[:-2]
            recv_crc = (response[-1] << 8) | response[-2]
            if modbus_crc16(data) != recv_crc:
                return None

            byte_count = response[2]
            values = []
            for i in range(0, byte_count, 2):
                v = (response[3 + i] << 8) | response[4 + i]
                values.append(v)

            return values

    def write_single(self, address: int, value: int):
        with self.lock:
            if not self.sock and not self.connect():
                return None

            frame = struct.pack(">B B H H", self.slave_id, 6, address, value)
            crc = modbus_crc16(frame)
            frame += struct.pack("<H", crc)

            try:
                self.sock.sendall(frame)
                response = self.sock.recv(256)
            except Exception:
                self.connect()
                return None

            return response

    def write_multiple(self, address: int, values: List[int]):
        with self.lock:
            if not self.sock and not self.connect():
                return None

            count = len(values)
            byte_count = count * 2
            frame = struct.pack(">B B H H B", self.slave_id, 16, address, count, byte_count)
            for v in values:
                frame += struct.pack(">H", v)

            crc = modbus_crc16(frame)
            frame += struct.pack("<H", crc)

            try:
                self.sock.sendall(frame)
                response = self.sock.recv(256)
            except Exception:
                self.connect()
                return None

            return response

# ------------------------ FastAPI ------------------------


@router.get("/read")
def modbus_read(host: str, port: int, slave: int, start: int, count: int, func_code: int = 3):
    client = ModbusTCP(host, port, slave)
    result = client.read(start=start, count=count, func=func_code)
    return {"result": result}

@router.get("/write_single")
def modbus_write_single(host: str, port: int, slave: int, address: int, value: int):
    client = ModbusTCP(host, port, slave)
    result = client.write_single(address, value)
    return {"result": result}

@router.post("/write_multiple")
def modbus_write_multiple(host: str, port: int, slave: int, address: int, values: List[int]):
    client = ModbusTCP(host, port, slave)
    result = client.write_multiple(address, values)
    return {"result": result}





