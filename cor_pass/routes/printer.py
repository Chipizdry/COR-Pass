from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()  # Убрали prefix="/api" здесь

class Label(BaseModel):
    model_id: int
    content: str
    uuid: Optional[str] = None

class PrintRequest(BaseModel):
    labels: List[Label]

@router.post("/print_labels")
async def print_labels(data: PrintRequest):
    printer_url = "http://192.168.154.209:8080/task/new"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(printer_url, json=data.dict())
            if response.status_code == 200:
                return {"success": True, "printer_response": response.text}
            else:
                raise HTTPException(status_code=502, detail=f"Printer error: {response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send to printer: {str(e)}")