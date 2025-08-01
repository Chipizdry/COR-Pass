from fastapi import APIRouter, Form
from PIL import Image, ImageDraw, ImageFont
from brother_ql.raster import BrotherQLRaster
from brother_ql.conversion import convert
import socket
import uuid

router = APIRouter()

PRINTER_IP = "192.168.154.154"
PRINTER_MODEL = "QL-810W"
LABEL_TYPE = "62"

def send_lpr_job(printer_ip, queue_name, data):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((printer_ip, 515))

    def send_cmd(cmd):
        s.sendall(cmd.encode('ascii') + b'\n')

    # 1. Открываем print job
    send_cmd(f"\x02{queue_name}")
    if s.recv(1) != b'\x00':
        s.close()
        raise Exception("LPR: ошибка подтверждения команды печати")

    # 2. Control file
    control_file = f"H{socket.gethostname()}\nPuser\nfdfA123{queue_name}\nNlabel.txt\n"

    send_cmd(f"\x02{len(control_file)} cfA123{queue_name}")
    if s.recv(1) != b'\x00':
        s.close()
        raise Exception("LPR: ошибка подтверждения команды control file")

    s.sendall(control_file.encode('ascii') + b'\x00')
    if s.recv(1) != b'\x00':
        s.close()
        raise Exception("LPR: ошибка подтверждения отправки control file")

    # 3. Data file
    send_cmd(f"\x03{len(data)} dfA123{queue_name}")
    if s.recv(1) != b'\x00':
        s.close()
        raise Exception("LPR: ошибка подтверждения команды data file")

    s.sendall(data + b'\x00')
    if s.recv(1) != b'\x00':
        s.close()
        raise Exception("LPR: ошибка подтверждения отправки data file")

    s.close()


@router.post("/print_code_label")
def print_label(content: str = Form(...)):
    try:
        print("📦 Получен запрос на печать с текстом:", content)

        # Создание изображения
        img = Image.new("RGB", (696, 150), color="white")
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text((10, 50), content, fill="black", font=font)
        print("🖼️ Изображение создано")

        # Генерация инструкций для принтера
        qlr = BrotherQLRaster(PRINTER_MODEL)
        qlr.exception_on_warning = True

        convert(
            qlr=qlr,
            images=[img],
            label=LABEL_TYPE,
            rotate="90",
            threshold=70.0,
            dither=False,
            compress=True,
            red=False,
            dpi_600=False,
            hq=True,
            cut=True
        )
        print(f"📄 Инструкций байт: {len(qlr.data)}")

        # Отправка данных через LPR протокол на порт 515
        print(f"📡 Отправка данных на {PRINTER_IP}:515 через LPR ...")
        send_lpr_job(PRINTER_IP, "lp", qlr.data)
        print("✅ Отправка завершена")

        return {"status": "success"}

    except Exception as e:
        print("❌ Ошибка при печати:", str(e))
        return {"status": "error", "detail": str(e)}


