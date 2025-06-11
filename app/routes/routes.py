# app/routes/routes.py

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from botocore.exceptions import ClientError
from app.models import FacturaRequest, PdfToJsonRequest
from app.services.pdf_generator import generar_pdf
from app.services.pdf_tpl1 import upload_pdf_to_s3,s3_client
from app.services.auth import get_current_user
from app.services.pdf_parser import pdf_to_json_rut

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
        bucket = result["bucket"]
        try:
            s3_client.head_bucket(Bucket=bucket)
        except ClientError as err:
            msg = err.response.get("Error",{}).get("Message", str(err))
            return JSONResponse(
                status_code=400,
                content={"code":400, "error": f"S3 bucket inválido o innaccesible: {msg}"}
            )
            


        # 2) Programa la subida en background
        background_tasks.add_task(
            upload_pdf_to_s3,
            result["pdf_bytes"],
            result["bucket"],
            result["key"],
        )

        # 3) Construye la URL pública (sin esperar a la subida)
        region = os.getenv("S3_REGION")
        url = f"https://{result['bucket']}/{result['key']}"

        # 4) Responde con JSON y HTTP 200
        return JSONResponse(
            status_code=200,
            content={"code": 200, "url": url}
        )


    except ValueError as ve:
        return JSONResponse(
            status_code=400,
            content={"code": 200, "error": str(ve)}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"code":500, "error": f"Error interno al generar el pdf: {e}"}            
        )

@router.post("/parse_pdf/", response_model=dict)
async def convertir_pdf_a_json(
    payload: PdfToJsonRequest,
    user: dict = Depends(get_current_user),
):
    """
    Recibe en el body una URL pública a un PDF (RUT), lo descarga, lo parsea
    y devuelve un JSON con los campos extraídos.
    """
    try:
        resultado = pdf_to_json_rut(payload.pdf_url)
        if not resultado:
            # Si no se extrajo ningún campo, devolvemos 422
            raise HTTPException(
                status_code=422,
                detail="No se pudo extraer ningún dato del PDF proporcionado.",
            )
        return resultado

    except HTTPException:
        # Propagamos errores HTTP específicos
        raise
    except ValueError as ve:
        # Errores de validación propia (por ej., URL no es PDF)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        # Cualquier otro fallo interno
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")
