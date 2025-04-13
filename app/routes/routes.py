from fastapi import APIRouter, Depends, HTTPException
from app.models import FacturaRequest
from app.services.pdf_generator import generar_pdf
from app.services.auth import get_current_user

router = APIRouter()

@router.post("/generar_pdf/")
async def generar_pdf_endpoint(request: FacturaRequest, user: dict = Depends(get_current_user)):
    """
    Endpoint para generar un PDF de una única factura y obtener su nombre en S3.
    """
    try:
        # Generar el PDF con los datos directamente del objeto recibido
        pdf_filename = generar_pdf(request.dict())

        return {
            "mensaje": "PDF generado y subido a S3 correctamente",
            "archivo_s3": pdf_filename
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar el PDF: {str(e)}")
