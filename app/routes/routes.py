from fastapi import APIRouter, Depends, HTTPException
from app.models import FacturaRequest
from app.services.pdf_generator import generar_pdf
from app.services.auth import get_current_user

router = APIRouter()

@router.post("/generar_pdf/")
async def generar_pdf_endpoint(request: FacturaRequest, user: dict = Depends(get_current_user)):
    """
    Endpoint para generar PDFs de facturas y obtener sus nombres en S3.
    """
    try:
        facturas_generadas = []
        
        # Procesar cada factura en la lista de facturas
        for factura in request.facturas:
            pdf_filename = generar_pdf(factura.dict())  # Generar el PDF
            
            # Guardar el nombre del archivo generado
            facturas_generadas.append({"archivo_s3": pdf_filename})

        return {
            "mensaje": "PDFs generados y subidos a S3 correctamente",
            "facturas": facturas_generadas
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar el PDF: {str(e)}")

