




from fastapi import APIRouter, Response, HTTPException
import httpx
from loguru import logger
import os



router = APIRouter(prefix="/scanner", tags=["Scanner"])


SCANNER_IP = "192.168.154.164"   # IP твоего H ScanJet Pro
SCANNER_PORT = 8080              # может быть 443 или 80 
USERNAME = None                  # если  с паролем 
PASSWORD = None

SAVE_DIR = "/scans"

async def get_client():
  
    if USERNAME and PASSWORD:
        return httpx.AsyncClient(auth=(USERNAME, PASSWORD))
    return httpx.AsyncClient()


@router.get("/capabilities")
async def get_capabilities():
    """Показать возможности сканера (форматы, DPI и т.д.)."""
    url = f"http://{SCANNER_IP}:{SCANNER_PORT}/eSCL/ScannerCapabilities"
    async with await get_client() as client:
        try:
            r = await client.get(url, timeout=10)
            r.raise_for_status()
            return Response(content=r.text, media_type="application/xml")
        except Exception as e:
            logger.error(f"Ошибка получения Capabilities: {e}")
            raise HTTPException(status_code=500, detail="Сканер недоступен")


@router.get("/scan")
async def scan_document():
    """Сканирование и возврат изображения (JPEG)."""
    scan_settings = """<?xml version="1.0" encoding="UTF-8"?>
    <scan:ScanSettings xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03">
      <scan:InputSource>Platen</scan:InputSource>
      <scan:DocumentFormat>image/jpeg</scan:DocumentFormat>
      <scan:ColorMode>RGB24</scan:ColorMode>
      <scan:XResolution>300</scan:XResolution>
      <scan:YResolution>300</scan:YResolution>
    </scan:ScanSettings>
    """

    async with await get_client() as client:
        try:
            r = await client.post(
                f"http://{SCANNER_IP}:{SCANNER_PORT}/eSCL/ScanJobs",
                content=scan_settings,
                headers={"Content-Type": "application/xml"},
                timeout=20,
            )
            r.raise_for_status()
            job_url = r.headers.get("Location")
            if not job_url:
                raise HTTPException(status_code=500, detail="Сканер не вернул Location")

            doc = await client.get(f"http://{SCANNER_IP}:{SCANNER_PORT}{job_url}/NextDocument")
            doc.raise_for_status()
            return Response(content=doc.content, media_type="image/jpeg")
        except Exception as e:
            logger.error(f"Ошибка сканирования: {e}")
            raise HTTPException(status_code=500, detail="Ошибка сканирования")



@router.get("/scan_to_file")
async def scan_to_file(filename: str = "scan.jpg"):
    filepath = os.path.join(SAVE_DIR, filename)

    scan_settings = """<?xml version="1.0" encoding="UTF-8"?>
    <scan:ScanSettings xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03">
      <scan:InputSource>Platen</scan:InputSource>
      <scan:DocumentFormat>image/jpeg</scan:DocumentFormat>
      <scan:ColorMode>RGB24</scan:ColorMode>
      <scan:XResolution>300</scan:XResolution>
      <scan:YResolution>300</scan:YResolution>
    </scan:ScanSettings>
    """

    async with await get_client() as client:
        try:
            r = await client.post(
                f"http://{SCANNER_IP}:{SCANNER_PORT}/eSCL/ScanJobs",
                content=scan_settings,
                headers={"Content-Type": "application/xml"},
                timeout=20,
            )
            r.raise_for_status()
            job_url = r.headers.get("Location")
            if not job_url:
                raise HTTPException(status_code=500, detail="Сканер не вернул Location")

            doc = await client.get(f"http://{SCANNER_IP}:{SCANNER_PORT}{job_url}/NextDocument")
            doc.raise_for_status()

            os.makedirs(SAVE_DIR, exist_ok=True)  # создаём папку, если нет
            with open(filepath, "wb") as f:
                f.write(doc.content)

            return {"message": f"Скан сохранён в {filepath}"}
        except Exception as e:
            logger.error(f"Ошибка сканирования в файл: {e}")
            raise HTTPException(status_code=500, detail="Ошибка сканирования в файл")  