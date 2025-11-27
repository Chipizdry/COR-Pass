from fastapi import UploadFile, HTTPException, status

from cor_pass.services.shared.image_validation import ALLOWED_IMAGE_TYPES, validate_image_file


# Константы для валидации PDF
ALLOWED_PDF_TYPES = {"application/pdf"}
MAX_PDF_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Для рецептов
ALLOWED_FILE_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}
MAX_FILE_SIZE_MB = 10

PDF_MAGIC = b"%PDF"
JPEG_MAGIC = b"\xFF\xD8\xFF"
PNG_MAGIC = b"\x89PNG"


async def validate_prescription_file(file: UploadFile) -> bytes:
    """
    Валидирует файл рецепта:
      - проверяет размер
      - проверяет content_type (если указан)
      - проверяет сигнатуру файла (magic bytes)
    Возвращает содержимое файла (bytes).
    """
    content = await file.read()
    await file.seek(0)

    # размер
    size_mb = len(content) / 1024 / 1024
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Размер файла превышает {MAX_FILE_SIZE_MB} МБ",
        )


    ct = (file.content_type or "").lower()
    if ct and ct not in ALLOWED_FILE_TYPES:
        
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Недопустимый content-type: {ct}. Разрешены: {', '.join(ALLOWED_FILE_TYPES)}",
        )

    # проверяем сигнатуру 
    header_window = content[:1024]  
    if PDF_MAGIC in header_window:
        return content


    if header_window.startswith(JPEG_MAGIC):
        return content


    if header_window.startswith(PNG_MAGIC):
        return content

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Неподдерживаемый или повреждённый файл. Разрешены PDF, JPG, PNG.",
    )


async def validate_pdf_file(file: UploadFile):

    if file.size > MAX_PDF_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Файл PDF слишком большой. Максимальный размер: {MAX_PDF_FILE_SIZE // (1024 * 1024)}MB",
        )

    if file.content_type not in ALLOWED_PDF_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Файл должен быть PDF",
        )

    file_header = await file.read(4)
    await file.seek(0)
    if file_header != b"%PDF":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Файл не является корректным PDF",
        )

    file_ext = file.filename.split(".")[-1].lower()
    if file_ext != "pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Неподдерживаемое расширение файла - {file_ext}. Разрешен только 'pdf'",
        )

    return file


async def validate_document_file(file: UploadFile):
    try:
        await validate_image_file(file)
        return file
    except HTTPException as image_err:
        try:
            await validate_pdf_file(file)
            return file
        except HTTPException as pdf_err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Недопустимый формат файла. Разрешены: {', '.join(ALLOWED_IMAGE_TYPES)} и PDF. Ошибки: изображение - '{image_err.detail}', PDF - '{pdf_err.detail}'",
            )
