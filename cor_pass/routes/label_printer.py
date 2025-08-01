from fastapi import APIRouter, Form
from PIL import Image, ImageDraw, ImageFont
from brother_ql.raster import BrotherQLRaster
from brother_ql.conversion import convert
import socket
import uuid
import time
router = APIRouter()

PRINTER_IP = "192.168.154.154"
PRINTER_MODEL = "QL-810W"
LABEL_TYPE = "62"

def create_label_image(text, max_width=696, max_height=300):
    font = ImageFont.load_default()

    # Определяем высоту строки через textbbox
    temp_img = Image.new("RGB", (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)
    bbox = temp_draw.textbbox((0, 0), "Ay", font=font)
    line_height = bbox[3] - bbox[1]

    max_chars_per_line = 40
    lines = [text[i:i+max_chars_per_line] for i in range(0, len(text), max_chars_per_line)]
    height = min(max_height, line_height * len(lines) + 20)

    img = Image.new("RGB", (max_width, height), color="white")
    draw = ImageDraw.Draw(img)
    y = 10
    for line in lines:
        draw.text((10, y), line, fill="black", font=font)
        y += line_height

    print(f"Перед convert(): размер изображения {img.size}")
    return img
def send_lpr_job(printer_ip, queue_name, data):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((printer_ip, 515))

    def send_cmd(cmd):
        s.sendall(cmd.encode('ascii') + b'\n')

    # 1. Инициация очереди
    send_cmd(f"\x02{queue_name}")
    ack = s.recv(1)
    if ack != b'\x00':
        raise Exception(f"LPR: ошибка подтверждения очереди: {ack!r}")

    # 2. Control file (минимальный)
    control_file = (
        f"H{socket.gethostname()}\n"    # hostname
        f"Ppython\n"                    # person/user
        f"Jlabel\n"                     # job name
        f"l\n"                          # output to printer
        f"UdfA123{queue_name}\n"        # unlink data file
        f"Nlabel.prn\n"                 # name of source file
    )

    send_cmd(f"\x02{len(control_file)} cfA123{queue_name}")
    ack = s.recv(1)
    if ack != b'\x00':
        raise Exception(f"LPR: ошибка подтверждения control file: {ack!r}")

    s.sendall(control_file.encode('ascii') + b'\x00')
    ack = s.recv(1)
    if ack != b'\x00':
        raise Exception(f"LPR: ошибка подтверждения control file data: {ack!r}")

    time.sleep(0.1)

    # 3. Data file
    send_cmd(f"\x03{len(data)} dfA123{queue_name}")
    ack = s.recv(1)
    if ack != b'\x00':
        raise Exception(f"LPR: ошибка подтверждения команды data file: {ack!r}")

    s.sendall(data + b'\x00')
    ack = s.recv(1)
    if ack != b'\x00':
        raise Exception(f"LPR: ошибка подтверждения отправки data file: {ack!r}")

    s.close()


@router.post("/print_code_label")
def print_label(content: str = Form(...)):
    try:
        print("📦 Получен запрос на печать с текстом:", content)

        img = create_label_image(content)

        print(f"🖼️ Изображение создано, размер: {img.size}")

        img = resize_image(img, max_width=696, max_height=300)
        print(f"🖼️ После resize_image(): размер {img.size}")

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
        print(f"📡 Отправка данных на {PRINTER_IP}:515 через LPR ...")
       # send_lpr_job(PRINTER_IP, "lp", qlr.data)
      #  send_lpr_job(PRINTER_IP, "raw", qlr.data)
        send_lpr_job(PRINTER_IP, "label", qlr.data)
        print("✅ Отправка завершена")

        return {"status": "success"}

    except Exception as e:
        print("❌ Ошибка при печати:", str(e))
        return {"status": "error", "detail": str(e)}


def resize_image(img, max_width=696, max_height=300):
    w, h = img.size
    scale_w = max_width / w
    scale_h = max_height / h
    scale = min(scale_w, scale_h, 1.0)  # не увеличиваем, только уменьшаем

    new_w = int(w * scale)
    new_h = int(h * scale)

    if (new_w, new_h) != (w, h):
        img = img.resize((new_w, new_h), Image.LANCZOS)
        print(f"🖼️ Изображение изменено с ({w},{h}) до ({new_w},{new_h})")

    return img