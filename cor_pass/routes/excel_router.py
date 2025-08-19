from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
import pandas as pd
import os
from pathlib import Path
from loguru import logger

router = APIRouter(prefix="/excel", tags=["Excel Operations"])

# Путь к файлу
EXCEL_FILE_PATH = Path("cor_pass/static/docs/register_map.xlsx")

@router.get("/process-register-map/", response_class=HTMLResponse)
async def process_register_map():
    """
    Обработка Excel файла и возврат HTML представления для модального окна
    """
    try:
        
        if not EXCEL_FILE_PATH.exists():
            raise HTTPException(status_code=404, detail="Excel file not found")
        
        # Читаем Excel файл
        df = pd.read_excel(EXCEL_FILE_PATH)
        
        processed_df = df.copy()
        if 'Amount' in processed_df.columns:
            processed_df['Amount'] = processed_df['Amount'] * 0.7  #  уменьшение на 70%
        
        # Конвертируем DataFrame в HTML таблицу
        html_table = processed_df.to_html(
            index=False,
            classes="excel-preview-table",
            border=0,
            justify="left"
        )
        
        # Создаем полный HTML ответ
        html_content = f"""
        <div class="excel-modal-content">
            <div class="table-container">
                {html_table}
            </div>
        </div>
        """
        
        return HTMLResponse(content=html_content)
    
    except Exception as e:
        logger.error(f"Error processing Excel file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@router.get("/download-register-map/")
async def download_register_map():
    """
    Скачивание обработанного Excel файла
    """
    try:
        # Здесь можно добавить дополнительную обработку перед скачиванием
        return FileResponse(
            EXCEL_FILE_PATH,
            filename="processed_register_map.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")