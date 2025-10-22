from datetime import datetime
from urllib.parse import urlparse
from reportlab.lib import pagesizes, colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas as canvas_module
from io import BytesIO
from starlette.concurrency import run_in_threadpool
from dotenv import load_dotenv
import boto3, os

# Cargar variables de entorno
load_dotenv()
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION")

# Cliente S3
s3_client = boto3.client("s3", region_name=S3_REGION)

# ----------------------------
# Utilidades
# ----------------------------
def hex_to_rgb_color(hex_string: str) -> Color:
    if not hex_string:
        return colors.HexColor("#044b5b")
    hex_string = hex_string.lstrip("#")
    r, g, b = tuple(int(hex_string[i:i+2], 16) for i in (0, 2, 4))
    return Color(r/255.0, g/255.0, b/255.0)

class NumberedCanvas(canvas_module.Canvas):
    def __init__(self, *args, factura=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.factura = factura
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_number(total)
            super().showPage()
        super().save()

    def _draw_page_number(self, total):
        self.setFont("Helvetica", 6)
        self.setFillColor(colors.black)
        page_width, _ = self._pagesize
        self.drawRightString(page_width - 28, 30, f"Página {self._pageNumber} de {total}")

# ----------------------------
# Secciones
# ----------------------------
def seccion_datos_liquidacion(factura, elements, header_color):
    titulo_style = ParagraphStyle(
        "titulo", fontSize=9, textColor=colors.whitesmoke, alignment=1, fontName="Helvetica-Bold"
    )
    data = [
        [Paragraph("<b>Datos de la liquidación</b>", titulo_style)],
        [f"{factura['otros'].get('variable_1','')}"],
        [f"{factura['otros'].get('variable_2','')}"],
        [f"Usuario liquidador: {factura['documento'].get('usuario_liquidador','')}"],
        [f"Fecha liquidación: {factura['documento'].get('fecha','')}"]
    ]
    tbl = Table(data, colWidths=[500])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        # sin grilla interna
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 1), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 2),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 8))

def seccion_trabajador(factura, elements, header_color):
    trabajador = factura["receptor"]
    salario = ""
    for d in factura.get("devengos", []):
        if d.get("tipo", "").lower() == "salario":
            salario = f"${float(d.get('valor', 0)):,.0f}"
            break
    dias = factura["otros"].get("variable_3", "")

    titulo_style = ParagraphStyle(
        "titulo", fontSize=9, textColor=colors.whitesmoke, alignment=1, fontName="Helvetica-Bold"
    )
    data = [
        [Paragraph("<b>Información del trabajador</b>", titulo_style)],
        [f"{trabajador['identificacion']} - {trabajador['nombre']}"],
        [f"Salario Base: {salario}"],
        [f"{dias}"],
    ]
    tbl = Table(data, colWidths=[500])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        # sin grilla interna
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 1), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 2),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 8))

def tabla_detalle(titulo, items, total, header_color):
    styles = getSampleStyleSheet()
    header = [Paragraph(f"<b>{titulo}</b>", ParagraphStyle(
        "titulo", fontSize=9, textColor=colors.whitesmoke, alignment=1
    ))]
    data = [header, ["Tipo", "Valor", "Observación"]]
    for d in items:
        data.append([
            d.get("tipo", ""),
            f"${float(d.get('valor', 0)):,.0f}",
            d.get("descripcion", "")
        ])
    data.append([
        Paragraph(f"<b>Total {titulo}</b>", styles["Normal"]),
        "",
        f"${float(total or 0):,.0f}"
    ])
    tbl = Table(data, colWidths=[200, 100, 200])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("BACKGROUND", (0, 1), (-1, 1), colors.lightgrey),
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("GRID", (0, 1), (-1, -1), 0.5, colors.grey),
    ]))
    return tbl

def seccion_neto(factura, elements, header_color):
    neto = factura.get("valor_nomina", {}).get("valor_total_pago", "0")
    data = [[Paragraph(
        f"<b>Neto a pagar: ${float(neto):,.0f}</b>",
        ParagraphStyle("titulo", fontSize=9, textColor=colors.whitesmoke, alignment=1)
    )]]
    tbl = Table(data, colWidths=[500])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 8))

# ----------------------------
# Generar PDF
# ----------------------------
def generar_pdf(factura):
    buffer = BytesIO()
    papel = factura.get("caracteristicas", {}).get("papel", "LETTER").upper()
    try:
        page_size = getattr(pagesizes, papel)
    except AttributeError:
        page_size = pagesizes.LETTER

    pdf = SimpleDocTemplate(
        buffer, pagesize=page_size, leftMargin=28, rightMargin=28, topMargin=28, bottomMargin=28
    )

    # Colores base
    base_color = hex_to_rgb_color(
        factura.get("caracteristicas", {}).get("color_fondo", "#044b5b")
    )
    colores = (factura.get("caracteristicas", {}) or {}).get("color_personalizado_campos", {}) or {}

    color_info      = hex_to_rgb_color(colores.get("color_info")) if colores.get("color_info") else base_color
    color_negativo  = hex_to_rgb_color(colores.get("color_negativo")) if colores.get("color_negativo") else base_color
    color_positivo  = hex_to_rgb_color(colores.get("color_positivo")) if colores.get("color_positivo") else base_color

    elements = []

    # Secciones con colores por categoría
    seccion_datos_liquidacion(factura, elements, color_info)       # info
    seccion_trabajador(factura, elements, color_positivo)          # positivo

    elements.append(
        tabla_detalle("Devengos", factura.get("devengos", []),
                      factura.get("valor_nomina", {}).get("valor_total_devengos", "0"),
                      color_positivo)
    )
    elements.append(Spacer(1, 8))

    elements.append(
        tabla_detalle("Deducciones", factura.get("deducciones", []),
                      factura.get("valor_nomina", {}).get("valor_total_deducciones", "0"),
                      color_negativo)
    )
    elements.append(Spacer(1, 8))

    seccion_neto(factura, elements, color_info)                     # info

    elements.append(
        tabla_detalle("Aportes del Empleador", factura.get("aportes_empleador", []),
                      factura.get("valor_nomina", {}).get("valor_total_empleador", "0"),
                      color_info)
    )
    elements.append(Spacer(1, 8))

    elements.append(
        tabla_detalle("Provisiones Prestaciones Sociales", factura.get("prestaciones_sociales", []),
                      factura.get("valor_nomina", {}).get("valor_total_prestaciones", "0"),
                      color_info)
    )
    elements.append(Spacer(1, 8))

    pdf.build(
        elements,
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(*args, factura=factura, **kwargs),
    )

    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    hoy = datetime.now()
    pdf_filename = f"nomina_{factura['documento']['identificacion']}_{hoy.strftime('%Y%m%d_%H%M%S_%f')[:-3]}.pdf"

    ruta_doc = factura["documento"].get("ruta_documento")
    if ruta_doc:
        parsed = urlparse(str(ruta_doc))
        bucket_name = parsed.netloc
        key = parsed.path.lstrip("/")
    else:
        bucket_name = S3_BUCKET_NAME
        key = (
            f"{factura['receptor']['identificacion']}/"
            f"{hoy.year}/{hoy.month:02d}/{hoy.day:02d}/"
            f"{pdf_filename}"
        )

    return {"pdf_bytes": pdf_bytes, "bucket": bucket_name, "key": key, "filename": pdf_filename}

# ----------------------------
# Subida a S3
# ----------------------------
def _sync_upload(pdf_bytes: bytes, bucket: str, key: str):
    print(f"[sync_upload] subiendo {len(pdf_bytes)} bytes a s3://{bucket}/{key}")
    try:
        buf = BytesIO(pdf_bytes)
        s3_client.upload_fileobj(
            buf, bucket, key,
            ExtraArgs={"ContentType": "application/pdf", "ContentDisposition": "inline"},
        )
        print(f"[sync_upload] ¡Subida completada! s3://{bucket}/{key}")
    except Exception as e:
        print(f"[sync_upload] ERROR al subir: {e}")
        raise

async def upload_pdf_to_s3(pdf_bytes: bytes, bucket: str, key: str):
    print(f"[upload_pdf_to_s3] llamada recibida para {bucket}/{key}")
    await run_in_threadpool(_sync_upload, pdf_bytes, bucket, key)
    print(f"[upload_pdf_to_s3] función async finalizada para {bucket}/{key}")
