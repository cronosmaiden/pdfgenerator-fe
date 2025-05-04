from .pdf_tpl1 import generar_pdf as generar_pdf_tpl1
from .pdf_tpl2 import generar_pdf as generar_pdf_tpl2

def generar_pdf(factura):
    # 1) Extraemos el valor de plantilla desde caracteristicas.plantilla (por defecto = 1)
    plantilla = factura.get("caracteristicas", {}).get("plantilla", 1)
    try:
        plantilla = int(plantilla)
    except (TypeError, ValueError):
        plantilla = 1

    # 2) Despacho EXACTO a cada módulo
    if plantilla == 1:
        return generar_pdf_tpl1(factura)
    elif plantilla == 2:
        return generar_pdf_tpl2(factura)
    else:
        raise ValueError(f"Plantilla desconocida: {plantilla}. Solo se admite 1 o 2.")