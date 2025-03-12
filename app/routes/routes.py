from fastapi import APIRouter, Depends
from app.models import FacturaData
from app.services.pdf_generator import generar_pdf
from app.services.auth import get_current_user

router = APIRouter()

@router.post("/generar_pdf/")
async def generar_pdf_endpoint(factura: FacturaData, user: dict = Depends(get_current_user)):
    pdf_filename = generar_pdf(factura)
    return {"mensaje": "Archivo subido correctamente", "archivo_s3": pdf_filename}
