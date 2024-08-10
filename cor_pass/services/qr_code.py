from io import BytesIO
import qrcode

from PIL import ImageDraw, ImageFont


def generate_qr_code(data: str, signature: str) -> bytes:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Добавление подписи
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(
        "arial.ttf", 16
    )  
    text_width = 200  # Фиксированная ширина текста
    text_height = 30  # Фиксированная высота текста
    draw.text(
        ((img.size[0] - text_width) // 2, img.size[1] - text_height - 5),
        signature,
        fill="black",
        font=font,
        align="center",
    )

    buffered = BytesIO()
    img.save(buffered)
    img_bytes = buffered.getvalue()

    return img_bytes
