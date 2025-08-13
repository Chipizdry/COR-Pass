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
QUEUE_NAMES = ["lp", "LPT1", "PRINTER", "Brother", "label", "raw"] 



def create_label_image(text, max_width=696, max_height=300):
    font = ImageFont.load_default()
    temp_img = Image.new("RGB", (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)
    bbox = temp_draw.textbbox((0, 0), "Ay", font=font)
    line_height = bbox[3] - bbox[1]

    lines = [text[i:i+40] for i in range(0, len(text), 40)]
    height = min(max_height, line_height * len(lines) + 20)

    img = Image.new("RGB", (max_width, height), color="white")
    draw = ImageDraw.Draw(img)
    y = 10
    for line in lines:
        draw.text((10, y), line, fill="black", font=font)
        y += line_height

    print(f"🖼️ Создано изображение {img.size}")
    return img


def try_lpr_print(data):
    """Попытка печати через LPR протокол"""
    queues = ["raw", "lp", "LPT1", "PRINTER", "Brother", "label"]
    
    for queue in queues:
        try:
            print(f"\n🔄 Попытка LPR печати через очередь '{queue}'")
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(10)
                s.connect((PRINTER_IP, 515))
                
                # 1. Инициализация
                s.sendall(f"\x02{queue}\n".encode())
                response = s.recv(1)
                print(f"← Ответ инициализации: {response!r}")
                
                # 2. Control file
                cf = f"H{socket.gethostname()[:31]}\nPpython\nJlabel\nldfA{queue}\n"
                s.sendall(f"\x02{len(cf)} cfA{queue}\n".encode())
                s.recv(1)
                s.sendall(cf.encode() + b'\x00')
                s.recv(1)
                
                # 3. Data file
                s.sendall(f"\x03{len(data)} dfA{queue}\n".encode())
                s.recv(1)
                s.sendall(data + b'\x00')
                final_response = s.recv(1)
                
                if final_response == b'\x00':
                    print(f"✅ Успешная печать через '{queue}'")
                    return True
                
        except Exception as e:
            print(f"⚠ Ошибка: {str(e)}")
            continue
    
    return False

def try_system_lpr(data):
    """Попытка печати через системную команду lpr"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".prn") as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        
        cmd = f"lpr -S {PRINTER_IP} -P raw -o raw {tmp_path}"
        print(f"\n🔄 Попытка системной печати: {cmd}")
        
        result = subprocess.run(
            cmd.split(),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Успешная отправка через lpr")
            return True
            
        print(f"❌ Ошибка lpr: {result.stderr}")
        return False
        
    except Exception as e:
        print(f"⚠ Ошибка системной печати: {str(e)}")
        return False
    finally:
        import os
        if 'tmp_path' in locals():
            os.unlink(tmp_path)

def send_lpr_job(printer_ip, queue_name, data, timeout=10):  # Увеличен таймаут
    s = None
    try:
        print(f"\n⌛ Подключаюсь к {printer_ip}:515 (очередь: '{queue_name}')...")
        start_time = time.time()
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8192)
        s.connect((printer_ip, 515))
        print(f"✓ Подключено за {(time.time()-start_time):.2f}с")

        def send_and_check(cmd, description=""):
            print(f"→ [{description}] Отправка: {cmd[:64]}...")
            s.sendall(cmd.encode('ascii') + b'\n')
            response = s.recv(1024)
            print(f"← Ответ: {response!r}")
            return response

        # 1. Инициализация очереди
        print("\n=== 1. ИНИЦИАЛИЗАЦИЯ ОЧЕРЕДИ ===")
        response = send_and_check(f"\x02{queue_name}", "Инициализация")
        if response != b'\x00':
            print(f"⚠ Некорректный ответ на инициализацию: {response!r}")

        # 2. Control file
        print("\n=== 2. CONTROL FILE ===")
        control_file = (
            f"H{socket.gethostname()[:31]}\n"
            f"Ppython_script\n"
            f"Jlabel_print\n"
            f"ldfA{queue_name}\n"
            f"Nprintjob_{uuid.uuid4().hex[:8]}\n"
        )
        print(f"📄 Control file content:\n{control_file}")

        response = send_and_check(f"\x02{len(control_file)} cfA{queue_name}", "Размер control file")
        if response != b'\x00':
            raise Exception(f"Ошибка подтверждения control file: {response!r}")

        print("⌛ Отправляю control file...")
        s.sendall(control_file.encode('ascii') + b'\x00')
        response = s.recv(1024)
        print(f"← Ответ на control file: {response!r}")

        # 3. Data file
        print("\n=== 3. DATA FILE ===")
        response = send_and_check(f"\x03{len(data)} dfA{queue_name}", "Размер data file")
        if response != b'\x00':
            raise Exception(f"Ошибка подтверждения data file: {response!r}")

        # Отправка данных с прогрессом
        print(f"⌛ Отправка {len(data)} байт данных...")
        chunk_size = 4096
        for i in range(0, len(data), chunk_size):
            s.sendall(data[i:i+chunk_size])
            if i % (chunk_size*10) == 0:  # Логируем прогресс каждые 40KB
                print(f"↳ Отправлено {i/1024:.1f}KB из {len(data)/1024:.1f}KB")
        
        s.sendall(b'\x00')
        response = s.recv(1024)
        print(f"← Финальный ответ: {response!r}")

        if response == b'\x00':
            print("\n✅ Данные успешно приняты принтером")
            return True
        raise Exception(f"Ошибка подтверждения печати: {response!r}")

    except socket.timeout:
        print("\n⌛ Таймаут операции!")
        raise Exception(f"Таймаут ({timeout}с) при работе с принтером")
    except ConnectionRefusedError:
        print("\n❌ Подключение отклонено")
        raise Exception("Принтер отказал в подключении")
    except Exception as e:
        print(f"\n❌ Ошибка: {str(e)}")
        raise
    finally:
        if s:
            s.close()
            print("🔌 Соединение закрыто")


@router.post("/print_code_label")
def print_label(content: str = Form(...)):
    print("\n" + "="*50)
    print(f"🆕 Запрос на печать: '{content[:32]}...'")
    
    try:
        # Создание изображения
        img = create_label_image(content)
        
        # Конвертация в QL-формат
        qlr = BrotherQLRaster(PRINTER_MODEL)
        convert(
            qlr=qlr,
            images=[img],
            label=LABEL_TYPE,
            rotate="90",
            cut=True
        )
        print(f"📦 Размер данных: {len(qlr.data)/1024:.1f}KB")

        # 1. Попытка через LPR
        if try_lpr_print(qlr.data):
            return {"status": "success", "method": "lpr"}
        
        # 2. Попытка через системный lpr
        if try_system_lpr(qlr.data):
            return {"status": "success", "method": "system_lpr"}
            
        raise Exception("Все методы печати не сработали")

    except Exception as e:
        print(f"\n❌ Ошибка: {str(e)}")
        return {"status": "error", "detail": str(e)}


        

def resize_image(img, max_width=696, max_height=300):
    w, h = img.size
    scale = min(max_width/w, max_height/h, 1.0)
    new_w, new_h = int(w*scale), int(h*scale)
    
    if (new_w, new_h) != (w, h):
        img = img.resize((new_w, new_h), Image.LANCZOS)
        print(f"🖼️ Изменен размер: {w}x{h} → {new_w}x{new_h}")
    
    return img


def check_printer_available(ip, port=515, timeout=3):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((ip, port))
            return True
    except Exception as e:
        print(f"❌ Проверка подключения: {str(e)}")
        return False