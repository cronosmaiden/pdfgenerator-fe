from datetime import datetime
from urllib.parse import urlparse
from reportlab.lib import pagesizes, colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import Color
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as canvas_module
from io import BytesIO
from starlette.concurrency import run_in_threadpool
from dotenv import load_dotenv
from app.services.qr_generator import generar_qr
import boto3
import os
import base64

# Cargar variables de entorno
load_dotenv()
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION")

# Cliente S3
s3_client = boto3.client("s3", region_name=S3_REGION)

PAGE_PARAMS = {
    "LETTER": {
        "header_height_first": 180,
        "header_height_later":  90,
        "footer_height":        80,
        "Y_NOTAS":              72,
        "Y_DIRECCION":          65,
        "Y_AUTORRETE":          50,
    },
    "LEGAL": {
        "header_height_first": int(180 * 1.273),
        "header_height_later":  int(90  * 1.273),
        "footer_height":        int(80  * 1.273),
        "Y_NOTAS":              int(72  * 1.273),
        "Y_DIRECCION":          int(65  * 1.273),
        "Y_AUTORRETE":          int(50  * 1.273),
    },
    "A4": {
        "header_height_first": int(180 * 1.063),
        "header_height_later":  int(90  * 1.063),
        "footer_height":        int(80  * 1.063),
        "Y_NOTAS":              int(72  * 1.063),
        "Y_DIRECCION":          int(65  * 1.063),
        "Y_AUTORRETE":          int(50  * 1.063),
    },
    "HALFLETTER": {
        "header_height_first": int(180 * (612/792)),
        "header_height_later":  int(90  * (612/792)),
        "footer_height":        int(80  * (612/792)),
        "Y_NOTAS":              int(72  * (612/792)),
        "Y_DIRECCION":          int(65  * (612/792)),
        "Y_AUTORRETE":          int(50  * (612/792)),
    },
}

# ----------------------------
# Utilidades
# ----------------------------
def hex_to_rgb_color(hex_string: str) -> Color:
    if not hex_string:
        return colors.HexColor("#044b5b")
    hex_string = hex_string.lstrip("#")
    r, g, b = tuple(int(hex_string[i:i+2], 16) for i in (0, 2, 4))
    return Color(r/255.0, g/255.0, b/255.0)

def agregar_marca_agua(canvas, factura):
    texto_marca = factura["documento"].get("marca_agua", "")
    if not texto_marca:
        return

    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 50)
    canvas.setFillGray(0.85, 0.4)

    width, height = canvas._pagesize
    canvas.translate(width / 2, height / 2)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, texto_marca.upper())

    canvas.restoreState()

def agregar_direccion_contacto(canvas, doc, factura):
    canvas.saveState()
    emisor = factura['emisor']
    # Usar telefono si num_celular está vacío
    telefono = emisor.get('num_celular') or emisor.get('telefono', '')

    direccion_texto = (
        f"Dir.: {emisor.get('direccion', '')} {emisor.get('ciudad', '')}, "
        f"Tel.: {telefono}, "
        f"Email: {emisor.get('email', '')} | "
        f"Web: {emisor.get('sitio_web', '')}"
    )
    canvas.setFont("Helvetica", 7)
    page_width = doc.pagesize[0]

    y = getattr(doc, "Y_DIRECCION", 65)
    canvas.drawCentredString(page_width/2, y, direccion_texto)
    canvas.restoreState()

def agregar_autorretenedores(canvas, doc, factura):
    canvas.saveState()

    notas_texto = factura.get("documento", {}) \
                       .get("notas_pie_pagina",
                            "Autorretenedores: Información no disponible.")

    estilo_auto = ParagraphStyle(
        name="Autorretenedores",
        fontName="Helvetica",
        fontSize=7,
        leading=7,
        alignment=1,
        spaceBefore=0,
        spaceAfter=0,
    )

    p = Paragraph(notas_texto, estilo_auto)

    ancho_disponible = doc.pagesize[0] - (doc.leftMargin + doc.rightMargin)

    w, h = p.wrap(ancho_disponible, doc.bottomMargin)

    x = doc.leftMargin
    y = getattr(doc, "Y_AUTORRETE", 50)
    p.drawOn(canvas, doc.leftMargin, y)
    canvas.restoreState()

def agregar_pie_pagina(canvas, doc, factura):
    color_texto_footer_hex = factura.get("caracteristicas", {}).get("pie_de_pagina", {}).get("Color_texto", "#000000")
    color_texto_footer_rgb = hex_to_rgb_color(color_texto_footer_hex)
    canvas.saveState()

    proveedor_texto = factura['afacturar']['info_pt']

    page_width = doc.pagesize[0]
    text_y = 30

    canvas.setFont("Helvetica", 6)

    canvas.setFillColor(color_texto_footer_rgb)

    canvas.drawCentredString(page_width / 2 - 40, text_y, proveedor_texto)

    logo_base64 = factura.get("afacturar", {}).get("logo", None)

    if logo_base64:
        try:
            logo_data = base64.b64decode(logo_base64)
            logo_buffer = BytesIO(logo_data)
            logo_image = ImageReader(logo_buffer)

            logo_width = 79
            logo_height = 20
            logo_x = page_width / 2 + 130
            logo_y = text_y - 6

            canvas.drawImage(logo_image, logo_x, logo_y, width=logo_width, height=logo_height, mask='auto')

        except Exception as e:
            print(f"Error al cargar la imagen del logo: {e}")

    canvas.restoreState()

def primera_pagina(canvas, doc, factura):

    titulo_pdf = f"{factura['documento']['identificacion']}@afacturar.com"
    canvas.setTitle(titulo_pdf)

    # Texto superior derecha: "Representación gráfica del documento electrónico"
    canvas.saveState()
    canvas.setFont("Helvetica", 6)
    canvas.setFillColor(colors.grey)
    page_width, page_height = canvas._pagesize
    x = page_width - 28
    y = page_height - 10
    canvas.drawRightString(x, y, "Representación gráfica del documento electrónico")
    canvas.restoreState()

    agregar_marca_agua(canvas, factura)
    agregar_direccion_contacto(canvas, doc, factura)
    agregar_autorretenedores(canvas, doc, factura)
    agregar_pie_pagina(canvas, doc, factura)

    # Fecha de validación DIAN en lateral izquierdo
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(colors.grey)
    _, page_height = doc.pagesize
    canvas.translate(15, page_height/2)  # centrado vertical aprox.
    canvas.rotate(90)
    canvas.drawString(0, 0, f"Fecha de validación DIAN: {factura['documento']['fecha_validacion_dian']}")
    canvas.restoreState()

def paginas_siguientes(canvas, doc, factura):

    # Texto superior derecha: "Representación gráfica del documento electrónico"
    canvas.saveState()
    canvas.setFont("Helvetica", 6)
    canvas.setFillColor(colors.grey)
    page_width, page_height = canvas._pagesize
    x = page_width - 28
    y = page_height - 10
    canvas.drawRightString(x, y, "Representación gráfica del documento electrónico")
    canvas.restoreState()

    agregar_marca_agua(canvas, factura)
    agregar_direccion_contacto(canvas, doc, factura)
    agregar_autorretenedores(canvas, doc, factura)
    agregar_pie_pagina(canvas, doc, factura)

    # Fecha de validación DIAN en lateral izquierdo
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(colors.grey)
    _, page_height = doc.pagesize
    canvas.translate(15, page_height/2)  # centrado vertical aprox.
    canvas.rotate(90)
    canvas.drawString(0, 0, f"Fecha de validación DIAN: {factura['documento']['fecha_validacion_dian']}")
    canvas.restoreState()

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
            self.draw_page_number(total)
            super().showPage()
        super().save()

    def draw_page_number(self, total):
        color_hex = self.factura.get("caracteristicas", {}).get("pie_de_pagina", {}).get("Color_texto", "#000000")
        color_rgb = hex_to_rgb_color(color_hex)

        self.setFont("Helvetica", 6)
        self.setFillColor(color_rgb)

        page_width, _ = self._pagesize
        page_num_text = f"Página {self._pageNumber} de {total}"
        self.drawRightString(page_width - 28, 30, page_num_text)

# ----------------------------
# Encabezado y Cliente
# ----------------------------
def agregar_encabezado(factura, elements, ancho_disponible):
    """Agrega el encabezado completo con logo grande izquierda, info emisor centro, caja documento derecha (SIN QR)"""
    styles = getSampleStyleSheet()

    # Razón social centrada arriba (negro, tamaño grande)
    razon_social_style = ParagraphStyle(
        name="RazonSocialTitle",
        fontName="Helvetica-Bold",
        fontSize=14,
        alignment=1,
        textColor=colors.black,
        spaceAfter=6
    )

    header_data = [
        [Paragraph(f"<b>{factura['emisor']['razon_social']}</b>", razon_social_style)]
    ]
    header_table = Table(header_data, colWidths=[ancho_disponible])
    header_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 12))

    # Información del emisor (centro, negro, labels bold)
    emisor = factura.get("emisor", {})

    label_style = ParagraphStyle(
        name="LabelEmisor",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=colors.black,
        alignment=0
    )
    value_style = ParagraphStyle(
        name="ValueEmisor",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.black,
        alignment=0
    )

    # Construir info_fija solo con campos que tengan datos
    info_fija = []

    # NIT siempre se muestra
    info_fija.append(Paragraph(f"<b>NIT:</b> {emisor.get('documento', 'N/A')}", label_style))

    # Solo agregar los siguientes campos si tienen valor
    if emisor.get('actividad_economica'):
        info_fija.append(Paragraph(f"<b>Actividad Económica:</b> {emisor.get('actividad_economica')}", label_style))

    if emisor.get('regimen'):
        info_fija.append(Paragraph(f"<b>Régimen:</b> {emisor.get('regimen')}", label_style))

    if emisor.get('responsable_iva'):
        info_fija.append(Paragraph(f"<b>Responsable IVA:</b> {emisor.get('responsable_iva')}", label_style))

    if emisor.get('tarifa_ica'):
        info_fija.append(Paragraph(f"<b>Tarifa ICA:</b> {emisor.get('tarifa_ica')}", label_style))

    # Logo del emisor (grande, izquierda)
    logo_ofe_b64 = factura.get("emisor", {}).get("logo")
    logo_ofe_img = None
    if logo_ofe_b64:
        try:
            # Soportar tanto base64 como URL
            if logo_ofe_b64.startswith("http"):
                import requests
                response = requests.get(logo_ofe_b64)
                logo_buffer = BytesIO(response.content)
                logo_ofe_img = Image(logo_buffer, width=120, height=80)
            else:
                logo_data = base64.b64decode(logo_ofe_b64)
                logo_buffer = BytesIO(logo_data)
                logo_ofe_img = Image(logo_buffer, width=120, height=80)
        except Exception as e:
            print(f"⚠️ Error al cargar logo_ofe: {e}")

    # QR Code (centro)
    qr_code = generar_qr(factura['documento']['qr'])
    qr_buffer = BytesIO(qr_code.getvalue())
    qr_image = Image(qr_buffer, width=80, height=80)

    # Caja de documento (derecha, 2 filas: título + identificación)
    doc_title_style = ParagraphStyle(
        name="DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.black,
        alignment=1
    )
    doc_id_style = ParagraphStyle(
        name="DocId",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.black,
        alignment=1
    )

    factura_info = Table([
        [Paragraph(f"<b>{factura['documento']['titulo_tipo_documento']}</b>", doc_title_style)],
        [Paragraph(f"<b>{factura['documento']['identificacion']}</b>", doc_id_style)]
    ], colWidths=[130])
    factura_info.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    # Layout: 4 columnas (logo | info | QR | doc)
    col_logo = 130
    col_qr = 90
    col_doc = 140
    col_info = ancho_disponible - col_logo - col_qr - col_doc

    header_row = Table([
        [[logo_ofe_img] if logo_ofe_img else [""], info_fija, qr_image, factura_info]
    ], colWidths=[col_logo, col_info, col_qr, col_doc])

    header_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),    # logo izquierda
        ("ALIGN", (1, 0), (1, 0), "LEFT"),    # info izquierda
        ("ALIGN", (2, 0), (2, 0), "CENTER"),  # QR centro
        ("ALIGN", (3, 0), (3, 0), "RIGHT"),   # doc derecha
    ]))

    elements.append(header_row)
    elements.append(Spacer(1, 12))

def agregar_info_trabajador(factura, elements, ancho_disponible):
    """Agrega la información del trabajador con título negro y tabla 4 columnas"""
    styles = getSampleStyleSheet()
    normal = styles["Normal"]

    # Estilos
    label_style = ParagraphStyle(
        name="LabelTrabajador",
        parent=normal,
        fontName="Helvetica",
        fontSize=7,
        leading=8,
        textColor=colors.black,
        alignment=0
    )

    value_style = ParagraphStyle(
        name="ValueTrabajador",
        parent=normal,
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8,
        textColor=colors.black,
        alignment=0
    )

    titulo_style = ParagraphStyle(
        name="TituloTrabajador",
        parent=normal,
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.whitesmoke,
        alignment=1
    )

    # Título gris oscuro
    titulo = Table([[Paragraph("Información del trabajador", titulo_style)]], colWidths=[ancho_disponible])
    titulo.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), colors.HexColor("#333333")),
        ("TEXTCOLOR",    (0, 0), (-1, -1), colors.whitesmoke),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("BOX",          (0, 0), (-1, -1), 1, colors.black),
        ("TOPPADDING",   (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
    ]))
    elements.append(titulo)

    # Tabla 4 columnas: Label1 | Value1 | Label2 | Value2
    receptor = factura["receptor"]
    documento = factura["documento"]

    col1_label = 95
    col2_value = 235
    col3_label = 95
    col4_value = ancho_disponible - col1_label - col2_value - col3_label

    data = [
        [Paragraph("Nombre:", label_style), Paragraph(receptor.get("nombre", ""), value_style),
         Paragraph("Teléfono:", label_style), Paragraph(receptor.get("numero_movil", ""), value_style)],

        [Paragraph("CC:", label_style), Paragraph(receptor.get("identificacion", ""), value_style), "", ""],

        [Paragraph("Correo Electrónico:", label_style), Paragraph(receptor.get("correo_electronico", ""), value_style), "", ""],

        [Paragraph("Dirección:", label_style), Paragraph(receptor.get("direccion", ""), value_style),
         Paragraph("Ciudad:", label_style), Paragraph(receptor.get("ciudad", ""), value_style)],

        [Paragraph("Departamento:", label_style), Paragraph(receptor.get("departamento", ""), value_style),
         Paragraph("País:", label_style), Paragraph(receptor.get("pais", ""), value_style)],

        [Paragraph("Moneda:", label_style), Paragraph(documento.get("moneda", ""), value_style),
         Paragraph("Banco:", label_style), Paragraph(documento.get("banco", ""), value_style)],

        [Paragraph("Tipo de pago:", label_style), Paragraph(documento.get("tipo_de_pago", ""), value_style),
         Paragraph("Cuenta bancaria:", label_style), Paragraph(documento.get("cuenta_bancaria", ""), value_style)],

        [Paragraph("Fecha y Hora de expedición:", label_style),
         Paragraph(f"{documento.get('fecha', '')} {documento.get('hora', '')}", value_style), "", ""],

        [Paragraph("Cargo:", label_style), Paragraph(receptor.get("cargo", ""), value_style),
         Paragraph("Tipo contrato:", label_style), Paragraph(receptor.get("tipo_contrato", ""), value_style)],

        [Paragraph("CUNE:", label_style), Paragraph(documento.get("cune", ""), value_style), "", ""],
    ]

    tabla = Table(data, colWidths=[col1_label, col2_value, col3_label, col4_value])
    tabla.setStyle(TableStyle([
        ("BOX",         (0, 0), (-1, -1), 1, colors.black),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
        # Spans para filas que ocupan ancho completo
        ("SPAN", (1, 1), (3, 1)),  # CC
        ("SPAN", (1, 2), (3, 2)),  # Correo
        ("SPAN", (1, 7), (3, 7)),  # Fecha expedición
        ("SPAN", (1, 9), (3, 9)),  # CUNE
    ]))

    elements.append(tabla)
    elements.append(Spacer(1, 8))

def agregar_periodo_pago(factura, elements, ancho_disponible):
    """Agrega la sección Periodo de pago con título negro y tabla 2 columnas"""
    styles = getSampleStyleSheet()
    normal = styles["Normal"]

    titulo_style = ParagraphStyle(
        name="TituloPeriodo",
        parent=normal,
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.whitesmoke,
        alignment=1
    )

    label_style = ParagraphStyle(
        name="LabelPeriodo",
        parent=normal,
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.black,
        alignment=0
    )

    value_style = ParagraphStyle(
        name="ValuePeriodo",
        parent=normal,
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=colors.black,
        alignment=0
    )

    # Título gris oscuro
    titulo = Table([[Paragraph("Periodo de pago", titulo_style)]], colWidths=[ancho_disponible])
    titulo.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), colors.HexColor("#333333")),
        ("TEXTCOLOR",    (0, 0), (-1, -1), colors.whitesmoke),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("BOX",          (0, 0), (-1, -1), 1, colors.black),
        ("TOPPADDING",   (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
    ]))
    elements.append(titulo)

    # Datos del periodo
    otros = factura.get("otros", {})

    # Tabla 4 columnas: Label1 | Value1 | Label2 | Value2
    data = [
        # Fila 1: Periodo desde y hasta
        [Paragraph("Periodo desde:", label_style), Paragraph(otros.get("variable_1", ""), value_style),
         Paragraph("Periodo hasta:", label_style), Paragraph(otros.get("variable_2", ""), value_style)],

        # Fila 2: Días trabajados y Vacaciones
        [Paragraph("Días trabajados:", label_style), Paragraph(otros.get("variable_3", ""), value_style),
         Paragraph("Vacaciones:", label_style), Paragraph("", value_style)],

        # Fila 3: Total (ocupa toda la fila)
        [Paragraph("Total:", label_style), Paragraph("", value_style), "", ""],
    ]

    col1_label = 120
    col2_value = int((ancho_disponible - 240) / 2)
    col3_label = 120
    col4_value = ancho_disponible - col1_label - col2_value - col3_label

    tabla = Table(data, colWidths=[col1_label, col2_value, col3_label, col4_value])
    tabla.setStyle(TableStyle([
        ("BOX",         (0, 0), (-1, -1), 1, colors.black),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
        # Span para Total (fila 2, desde columna 1 hasta 3)
        ("SPAN", (1, 2), (3, 2)),
    ]))

    elements.append(tabla)
    elements.append(Spacer(1, 8))

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
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("TOPPADDING", (0, 1), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 1),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 4))

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
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("TOPPADDING", (0, 1), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 1),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 4))

def tabla_detalle(titulo, items, total, header_color, ancho_disponible):
    """Tabla de devengos o deducciones con 3 columnas: Tipo, Valor, Observación"""
    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle(
        "titulo", fontSize=9, textColor=colors.whitesmoke, alignment=1, fontName="Helvetica-Bold"
    )

    # Estilo para observación con wrap automático
    observacion_style = ParagraphStyle(
        "observacion",
        parent=styles["Normal"],
        fontSize=8,
        leading=9,
        alignment=0,  # izquierda
        wordWrap='CJK'
    )

    # Fila de título
    data = [
        [Paragraph(f"<b>{titulo}</b>", titulo_style)],
        ["Tipo", "Valor", "Observación"]
    ]

    # Filas de items
    for d in items:
        tipo_text = d.get("tipo", "")
        valor_text = f"${float(d.get('valor', 0)):,.0f}"
        desc_text = d.get("descripcion", "")

        data.append([
            tipo_text,
            valor_text,
            Paragraph(desc_text, observacion_style)  # Usar Paragraph para wrap automático
        ])

    # Fila total
    total_style = ParagraphStyle(
        "total", fontSize=8, fontName="Helvetica-Bold", alignment=0
    )
    data.append([
        Paragraph(f"<b>Total {titulo}</b>", total_style),
        "",
        f"${float(total or 0):,.0f}"
    ])

    # Columnas proporcionales al ancho disponible
    col_tipo = int(ancho_disponible * 0.35)
    col_valor = int(ancho_disponible * 0.20)
    col_obs = ancho_disponible - col_tipo - col_valor

    tbl = Table(data, colWidths=[col_tipo, col_valor, col_obs])
    tbl.setStyle(TableStyle([
        # Encabezado: color + SPAN y centrado
        ("BACKGROUND", (0, 0), (-1, 0), header_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("SPAN", (0, 0), (-1, 0)),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, 0), 3),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 3),

        # Fila de cabeceras de columnas
        ("BACKGROUND", (0, 1), (-1, 1), colors.lightgrey),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("GRID", (0, 1), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("TOPPADDING", (0, 1), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 2),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("ALIGN", (2, 1), (2, -1), "LEFT"),
    ]))
    return tbl

def seccion_neto(factura, elements, header_color, ancho_disponible):
    neto = factura.get("valor_nomina", {}).get("valor_total_pago", "0")
    data = [[Paragraph(
        f"<b>Neto a pagar: ${float(neto):,.0f}</b>",
        ParagraphStyle("titulo", fontSize=9, textColor=colors.whitesmoke, alignment=1, fontName="Helvetica-Bold")
    )]]
    tbl = Table(data, colWidths=[ancho_disponible])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("TOPPADDING", (0, 0), (-1, 0), 4),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
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
        papel = "LETTER"
        page_size = pagesizes.LETTER

    page_width, page_height = page_size

    params = PAGE_PARAMS.get(papel, PAGE_PARAMS["LETTER"])

    pdf = SimpleDocTemplate(
        buffer, pagesize=page_size, leftMargin=28, rightMargin=28, topMargin=28, bottomMargin=28
    )

    pdf.Y_NOTAS     = params["Y_NOTAS"]
    pdf.Y_DIRECCION = params["Y_DIRECCION"]
    pdf.Y_AUTORRETE = params["Y_AUTORRETE"]

    # Calcular ancho disponible
    ancho_disponible = page_width - pdf.leftMargin - pdf.rightMargin

    # Colores según imagen 2: verde para devengos, rojo para deducciones, azul/teal para neto
    color_devengos = hex_to_rgb_color("#4CAF50")      # Verde
    color_deducciones = hex_to_rgb_color("#F44336")   # Rojo
    color_neto = hex_to_rgb_color("#00ACC1")          # Azul/Teal

    elements = []

    # Orden según imagen 2:
    # 1. Encabezado (sin QR, logo grande izquierda)
    agregar_encabezado(factura, elements, ancho_disponible)

    # 2. Información del trabajador (título negro, tabla 4 columnas)
    agregar_info_trabajador(factura, elements, ancho_disponible)

    # 3. Periodo de pago (título negro)
    agregar_periodo_pago(factura, elements, ancho_disponible)

    # 4. Devengos (barra verde)
    elements.append(
        tabla_detalle("Devengos", factura.get("devengos", []),
                      factura.get("valor_nomina", {}).get("valor_total_devengos", "0"),
                      color_devengos, ancho_disponible)
    )
    elements.append(Spacer(1, 8))

    # 5. Deducciones (barra roja)
    elements.append(
        tabla_detalle("Deducciones", factura.get("deducciones", []),
                      factura.get("valor_nomina", {}).get("valor_total_deducciones", "0"),
                      color_deducciones, ancho_disponible)
    )
    elements.append(Spacer(1, 8))

    # 6. Neto a pagar (barra azul/teal)
    seccion_neto(factura, elements, color_neto, ancho_disponible)

    pdf.build(
        elements,
        onFirstPage=lambda c, d: primera_pagina(c, d, factura),
        onLaterPages=lambda c, d: paginas_siguientes(c, d, factura),
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
