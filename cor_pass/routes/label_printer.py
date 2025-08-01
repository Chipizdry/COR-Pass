


from fastapi import APIRouter, Form
from PIL import Image, ImageDraw, ImageFont
from brother_ql.raster import BrotherQLRaster
from brother_ql.conversion import convert
from brother_ql.backends.network import send_over_network
import uuid

router = APIRouter()

PRINTER_IP = "192.168.154.154"  # IP  print server
PRINTER_MODEL = "QL-810W"
LABEL_TYPE = "62"  #  62 мм

@router.post("/print_code_label")
def print_label(content: str = Form(...)):
    try:
        print("📦 Получен запрос на печать с текстом:", content)

        # Шаг 1: Создание изображения
        img = Image.new("RGB", (696, 150), color="white")
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text((10, 50), content, fill="black", font=font)
        print("🖼️ Изображение создано")

        # Сохраняем изображение во временный файл (для отладки)
        img_path = f"/tmp/label_debug_{uuid.uuid4().hex}.png"
        img.save(img_path)
        print(f"💾 Изображение сохранено для отладки: {img_path}")

        # Шаг 2: Генерация инструкций
        qlr = BrotherQLRaster(PRINTER_MODEL)
        qlr.exception_on_warning = True
        print("🖨️ Raster принтера инициализирован")

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
        print("🔄 Инструкции преобразования сгенерированы")
        print(f"📄 Объём инструкций (байт): {len(qlr.data)}")

        # Шаг 3: Отправка на печать
        print(f"📡 Отправка на принтер {PRINTER_IP}:9100 ...")
        send_over_network(qlr, host=PRINTER_IP, port=9100)
        print("✅ Инструкции успешно отправлены")

        return {"status": "success"}

    except Exception as e:
        print("❌ Ошибка при печати:", str(e))
        return {"status": "error", "detail": str(e)}
