# app/routes/routes.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.models import FacturaRequest
from app.services.pdf_generator import generar_pdf
from app.services.pdf_tpl1 import upload_pdf_to_s3
from app.services.auth import get_current_user
import os

router = APIRouter()

@router.post("/generar_pdf/", status_code=200)
async def generar_pdf_endpoint(
    request: FacturaRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """
    Genera un PDF de la factura, lo envía YA al cliente en un JSON con la URL
    y sube el PDF a S3 en background.
    """
    try:
        # 1) Genera el PDF (bytes + metadatos S3)
        result = generar_pdf(request.dict())
        # result == {
        #   "pdf_bytes": b"...",
        #   "bucket": "mi-bucket",
        #   "key": "ruta/a/mi.pdf",
        #   "filename": "cufe_XXX_YYYYMMDD_HHMMSS.pdf"
        # }

        # 2) Programa la subida en background
        background_tasks.add_task(
            upload_pdf_to_s3,
            result["pdf_bytes"],
            result["bucket"],
            result["key"],
        )

        # 3) Construye la URL pública (sin esperar a la subida)
        region = os.getenv("S3_REGION")
        url = f"https://{result['bucket']}.s3.{region}.amazonaws.com/{result['key']}"

        # 4) Responde con JSON y HTTP 200
        return {"url": url}

    except Exception as e:
        # En caso de error, devolvemos HTTP 500 con JSON { error: "...mensaje..." }
        raise HTTPException(status_code=500, detail={"error": str(e)})
