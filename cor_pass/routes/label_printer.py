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





def send_lpr_job(printer_ip, queue_name, data, timeout=5):
    try:
        print(f"⌛ Подключение к {printer_ip}:515...")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        
        # Увеличиваем буфер для чтения
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8192)
        
        s.connect((printer_ip, 515))
        print("✓ Соединение установлено")

        def send_cmd(cmd):
            print(f"→ Отправка: {cmd[:100]}...")
            s.sendall(cmd.encode('ascii') + b'\n')
            response = s.recv(1024)  # Читаем больше данных
            print(f"← Ответ: {response!r}")
            return response

        # 1. Инициация очереди (без ожидания ACK)
        print("\n=== 1. ИНИЦИАЦИЯ ОЧЕРЕДИ ===")
        cmd = f"\x02{queue_name}"
        response = send_cmd(cmd)
        
        # Некоторые принтеры не требуют подтверждения на этом этапе
        if response and response != b'\x00':
            print(f"⚠ Неожиданный ответ: {response!r}")

        # 2. Control file (упрощенный)
        print("\n=== 2. CONTROL FILE ===")
        control_file = f"H{socket.gethostname()[:31]}\nPguest\nJlabel\nldfA{queue_name}\n"
        print(f"Content:\n{control_file}")

        cmd = f"\x02{len(control_file)} cfA{queue_name}"
        response = send_cmd(cmd)
        
        # Отправка данных control file
        s.sendall(control_file.encode('ascii') + b'\x00')
        response = s.recv(1024)
        print(f"Ответ на control file: {response!r}")

        # 3. Data file
        print("\n=== 3. DATA FILE ===")
        cmd = f"\x03{len(data)} dfA{queue_name}"
        response = send_cmd(cmd)
        
        # Отправка данных
        print(f"Отправка {len(data)} байт...")
        chunks = [data[i:i+1024] for i in range(0, len(data), 1024)]
        for chunk in chunks:
            s.sendall(chunk)
        s.sendall(b'\x00')
        
        response = s.recv(1024)
        print(f"Финальный ответ: {response!r}")
        
        return True

    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")
        raise
    finally:
        s.close()
        print("Соединение закрыто")




@router.post("/print_code_label")
def print_label(content: str = Form(...)):
    print("\n" + "="*50)
    print(f"🆕 Новый запрос на печать: '{content[:20]}...'")
    
    try:
        # Проверка доступности принтера
        print("🔍 Проверка доступности принтера...")
        if not check_printer_available(PRINTER_IP):
            msg = "Принтер недоступен"
            print(f"❌ {msg}")
            return {"status": "error", "detail": msg}

        # Создание изображения
        print("🖼️ Создание изображения...")
        img = create_label_image(content)
        print(f"🖼️ Размер изображения: {img.size}")

        # Конвертация в QL-формат
        print("🔄 Конвертация в формат Brother QL...")
        qlr = BrotherQLRaster(PRINTER_MODEL)
        convert(
            qlr=qlr,
            images=[img],
            label=LABEL_TYPE,
            rotate="90",
            threshold=70.0,
            dither=False,
            compress=True,
            cut=True
        )
        print(f"📦 Размер данных для печати: {len(qlr.data)} байт")

        # Попытка печати через разные очереди
        QUEUE_NAMES = ["lp", "LPT1", "PRINTER", "Brother", "label"]
        print(f"🖨️ Попытка печати через очереди: {QUEUE_NAMES}")
        
        for queue in QUEUE_NAMES:
            print(f"\n=== Попытка печати через очередь '{queue}' ===")
            try:
                if send_lpr_job(PRINTER_IP, queue, qlr.data):
                    print(f"✅ Успешная печать через очередь '{queue}'")
                    return {"status": "success"}
            except Exception as e:
                print(f"⚠️ Ошибка с очередью '{queue}': {str(e)}")
                continue

        raise Exception("Не удалось отправить на печать через все доступные очереди")

    except Exception as e:
        print(f"❌ Фатальная ошибка: {str(e)}")
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



def check_printer_available(ip, port=515, timeout=2):
    try:
        print(f"🔌 Проверка подключения к {ip}:{port}...")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((ip, port))
            print(f"✓ Принтер доступен")
            return True
    except Exception as e:
        print(f"❌ Ошибка подключения: {str(e)}")
        return False