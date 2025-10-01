from datetime import datetime
from urllib.parse import urlparse
from fastapi import HTTPException
from reportlab.lib import pagesizes
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.colors import Color
from io import BytesIO
from starlette.concurrency import run_in_threadpool
from reportlab.lib.utils import ImageReader
import boto3
import base64
import os
from app.services.qr_generator import generar_qr
from reportlab.pdfgen import canvas as canvas_module
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION")

# Cliente S3
s3_client = boto3.client(
    "s3",
    region_name=S3_REGION
)

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
        # valores escalados 1.273 = 1008/792
        "header_height_first": int(180 * 1.273),   # ≃229
        "header_height_later":  int(90  * 1.273),   # ≃114
        "footer_height":        int(80  * 1.273),   # ≃102
        "Y_NOTAS":              int(72  * 1.273),   # ≃ 92
        "Y_DIRECCION":          int(65  * 1.273),   # ≃ 83
        "Y_AUTORRETE":          int(50  * 1.273),   # ≃ 64
    },
    "A4": {
        # escala ≃842/792 = 1.063
        "header_height_first": int(180 * 1.063),   # ≃191
        "header_height_later":  int(90  * 1.063),   # ≃ 96
        "footer_height":        int(80  * 1.063),   # ≃ 85
        "Y_NOTAS":              int(72  * 1.063),   # ≃ 77
        "Y_DIRECCION":          int(65  * 1.063),   # ≃ 69
        "Y_AUTORRETE":          int(50  * 1.063),   # ≃ 53
    },
    "HALFLETTER": {  # media carta 396×612pt
        "header_height_first": int(180 * (612/792)),  # ≃139
        "header_height_later":  int(90  * (612/792)),  # ≃70
        "footer_height":        int(80  * (612/792)),  # ≃62
        "Y_NOTAS":              int(72  * (612/792)),  # ≃56
        "Y_DIRECCION":          int(65  * (612/792)),  # ≃50
        "Y_AUTORRETE":          int(50  * (612/792)),  # ≃38
    },
    # añade más tamaños dependiendo de los definidos en el json
}

# Conversión de color hexadecimal a RGB
def hex_to_rgb_color(hex_string: str) -> Color:
    hex_string = hex_string.lstrip("#")
    r, g, b = tuple(int(hex_string[i:i+2], 16) for i in (0, 2, 4))
    return Color(r/255.0, g/255.0, b/255.0)

# Funciones de pie y encabezado (mismo diseño que plantilla 1)
def agregar_marca_agua(canvas, factura):
    texto = factura["documento"].get("marca_agua", "")
    if not texto: return
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 50)
    canvas.setFillGray(0.85, 0.4)
    page_width, page_height = canvas._pagesize
    canvas.translate(page_width/2, page_height/2)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, texto.upper())
    canvas.restoreState()

def agregar_direccion_contacto(canvas, doc, factura):
    canvas.saveState()
    texto = (
        f"Dir.: {factura['emisor']['direccion']} {factura['emisor']['ciudad']}, "
        f"Tel.: {factura['emisor']['num_celular']}, "
        f"Email: {factura['emisor']['email']} | "
        f"Web: {factura['emisor']['sitio_web']}"
    )
    canvas.setFont("Helvetica", 7)
    page_width, _ = doc.pagesize
    y = getattr(doc, "Y_DIRECCION", 65)
    canvas.drawCentredString(page_width/2, y, texto)
    canvas.restoreState()

def agregar_autorretenedores(canvas, doc, factura):
    canvas.saveState()
    notas = factura.get("documento", {}).get("notas_pie_pagina", "Autorretenedores: Información no disponible.")
    canvas.setFont("Helvetica", 7)
    page_width, _ = doc.pagesize
    y = getattr(doc, "Y_AUTORRETE", 50)
    canvas.drawCentredString(page_width/2, y, notas)
    canvas.restoreState()

def agregar_pie_pagina(canvas, doc, factura):
    color_hex = factura.get("caracteristicas", {}).get("pie_de_pagina", {}).get("Color_texto", "#000000")
    color = hex_to_rgb_color(color_hex)
    canvas.saveState()
    texto = factura['afacturar']['info_pt']
    canvas.setFont("Helvetica", 6)
    canvas.setFillColor(color)
    page_width, _ = doc.pagesize
    canvas.drawCentredString(page_width/2 - 40, 30, texto)

    logo_b64 = factura.get("afacturar", {}).get("logo")
    if logo_b64:
        try:
            data = base64.b64decode(logo_b64)
            img = ImageReader(BytesIO(data))
            canvas.drawImage(img, page_width/2+130, 24, width=79, height=20, mask='auto')
        except:
            pass
    canvas.restoreState()

# **Funciones para manejar encabezado y pie de página correctamente**
def primera_pagina(canvas, doc, factura):
    
    #----titulo del pdf
    titulo_pdf = f"{factura['documento']['identificacion']}@afacturar.com"
    canvas.setTitle(titulo_pdf)
    # ——— Texto arriba-derecha ———
    canvas.saveState()
    canvas.setFont("Helvetica", 6)  # tamaño pequeño
    page_width, page_height = doc.pagesize
    x = page_width - 28            # tu margen derecho
    y = page_height - 10           # 10pt por debajo del borde superior
    canvas.drawRightString(x, y, factura["afacturar"]["titulo_superior"])
    canvas.restoreState()
    # ————————————————————

    agregar_marca_agua(canvas, factura)
    agregar_direccion_contacto(canvas, doc, factura)
    agregar_autorretenedores(canvas, doc, factura)
    agregar_pie_pagina(canvas, doc, factura)
    

    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(colors.grey)
    _, page_height = doc.pagesize
    canvas.translate(15, page_height/2)  # centrado vertical aprox.
    canvas.rotate(90)
    canvas.drawString(0, 0, f"Fecha de validación DIAN: {factura['documento']['fecha_validacion_dian']}")
    canvas.restoreState()

def paginas_siguientes(canvas, doc, factura):
    
    # ——— Texto arriba-derecha ———
    canvas.saveState()
    canvas.setFont("Helvetica", 6)  # tamaño pequeño
    page_width, page_height = doc.pagesize
    x = page_width - 28            # tu margen derecho
    y = page_height - 10           # 10pt por debajo del borde superior
    canvas.drawRightString(x, y, factura["afacturar"]["titulo_superior"])
    canvas.restoreState()
    # ————————————————————

    agregar_marca_agua(canvas, factura)
    agregar_direccion_contacto(canvas, doc, factura)
    agregar_autorretenedores(canvas, doc, factura)
    agregar_pie_pagina(canvas, doc, factura)

    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(colors.grey)
    _, page_height = doc.pagesize
    canvas.translate(15, page_height/2)
    canvas.rotate(90)
    canvas.drawString(0, 0, f"Fecha de validación DIAN: {factura['documento']['fecha_validacion_dian']}")
    canvas.restoreState()

# Canvas numerado
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
        color = hex_to_rgb_color(color_hex)
        self.setFont("Helvetica", 6)
        self.setFillColor(color)
        page_width, _ = self._pagesize   # 👈 dinámico
        self.drawRightString(page_width - 28, 30, f"Página {self._pageNumber} de {total}")

# Generación de PDF con lógica de plantilla 1

def generar_pdf(factura):
    buffer = BytesIO()
    papel = factura.get("caracteristicas", {}).get("papel", "letter").upper()
    try:
        page_size = getattr(pagesizes, papel)
    except AttributeError:
        papel = "LETTER"
        page_size = pagesizes.LETTER

    page_width, page_height = page_size
    params = PAGE_PARAMS.get(papel, PAGE_PARAMS["LETTER"])

    header1  = params["header_height_first"]
    headerN  = params["header_height_later"]
    footer_h = params["footer_height"]

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=28,
        rightMargin=28,
        topMargin=28,
        bottomMargin=28,
    )

    pdf.Y_DIRECCION = params["Y_DIRECCION"]
    pdf.Y_AUTORRETE = params["Y_AUTORRETE"]

    # Configuración márgenes según solo_primera y totales
    solo_primera = factura.get("caracteristicas", {}).get("encabezado", {}).get("solo_primera_pagina", 0)==1
    solo_ultima_totales = factura.get("caracteristicas", {}).get("totales", {}).get("solo_ultima_pagina",1)==1
    tot_h = 105
    header1 = 180
    headerN = 120 if solo_primera else 180
    footer_h = 80
    avail1 = page_height - pdf.topMargin - pdf.bottomMargin - header1 - footer_h
    availN = page_height - pdf.topMargin - pdf.bottomMargin - headerN - footer_h
    if not solo_ultima_totales:
        avail1 -= tot_h
        availN -= tot_h

    styles = getSampleStyleSheet()
    elements = []
    color_fondo = hex_to_rgb_color(factura.get("caracteristicas", {}).get("color_fondo","#808080"))
    color_enc = hex_to_rgb_color(factura.get("caracteristicas", {}).get("encabezado",{}).get("Color_texto","#000000"))

    def agregar_encabezado():
        razon_social_style = ParagraphStyle(
            name="RazonSocialTitle",
            fontName="Helvetica-Bold",
            fontSize=12,
            alignment=1,
            textColor=color_enc,
            spaceAfter=6
        )

        normal_color_style = ParagraphStyle(
            name="EncabezadoColorTexto",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            textColor=color_enc  # 👈 Nuevo
        )

        centered_bold_7 = ParagraphStyle(
            name="CenteredBold7",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            textColor=color_enc,
            alignment=1  # center
        )

        header_data = [
            [Paragraph(f"<b>{factura['emisor']['razon_social']}</b>", razon_social_style)]
        ]
        header_table = Table(header_data, colWidths=[500])
        header_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 20))

        # **Información Fija (Izquierda) + QR (Centro) + Factura Electrónica (Derecha)**
        emisor = factura.get("emisor", {})
        info_fija = [
            f"NIT: {emisor.get('documento', 'N/A')}",
            f"Actividad Económica: {emisor.get('actividad_economica', 'N/A')}",
            f"Régimen: {emisor.get('regimen', 'N/A')}",
            f"Responsable IVA: {emisor.get('responsable_iva', 'N/A')}",
            f"Tarifa ICA: {emisor.get('tarifa_ica', 'N/A')}"
        ]
        info_paragraphs = [Paragraph(f"<b>{line}</b>", normal_color_style) for line in info_fija]

        logo_ofe_b64 = factura.get("emisor", {}).get("logo")
        logo_ofe_img = None
        if logo_ofe_b64:
            try:
                logo_data = base64.b64decode(logo_ofe_b64)
                logo_buffer = BytesIO(logo_data)
                logo_ofe_img = Image(logo_buffer, width=90, height=60)  # Ajusta el tamaño si lo deseas
            except Exception as e:
                print(f"⚠️ Error al cargar logo_ofe: {e}")

        factura_info = Table([
            [Paragraph(f"<b>{factura['documento']['titulo_tipo_documento']}</b>", centered_bold_7)],
            [Paragraph(f"<b>{factura['documento']['identificacion']}</b>", centered_bold_7)]
        ], colWidths=[110])
        factura_info.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))

        header_row = Table([
            [[logo_ofe_img] if logo_ofe_img else [""],info_paragraphs, "", factura_info]
        ], colWidths=[140, 210, 100, 140])

        header_row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))

        elements.append(header_row)
        elements.append(Spacer(1, 8))

    # **Información del Cliente**
    def agregar_info_cliente():
        styles = getSampleStyleSheet()
        normal = styles["Normal"]

        # — Estilos —
        label_style = ParagraphStyle(
            name="LabelStyle", parent=normal,
            fontName="Helvetica",       # regular
            fontSize=7, leading=8,
            textColor=colors.black,
            alignment=0  # izq
        )
        header7 = ParagraphStyle(
            name="Header7", parent=normal,
            fontName="Helvetica-Bold",
            fontSize=7, leading=8,
            textColor=colors.whitesmoke,
            alignment=1  # centrar
        )
        value_left = ParagraphStyle(
            name="ValueLeft", parent=normal,
            fontName="Helvetica-Bold",  # negrita
            fontSize=7, leading=8,
            textColor=colors.black,
            alignment=0
        )
        value_center = ParagraphStyle(
            name="ValueCenter", parent=normal,
            fontName="Helvetica-Bold",  # negrita
            fontSize=7, leading=8,
            textColor=colors.black,
            alignment=1
        )

        # — Color de fondo dinámico —
        bg_hex   = factura.get("caracteristicas", {}).get("color_fondo", "#004d66")
        bg_color = hex_to_rgb_color(bg_hex)

        # — Valores en Paragraph para wrap y estilo —
        nombre       = Paragraph(factura["receptor"]["nombre"],        value_left)
        identific    = Paragraph(factura["receptor"]["identificacion"], value_left)
        direccion    = Paragraph(factura["receptor"]["direccion"],     value_left)
        telefono     = Paragraph(factura["receptor"]["numero_movil"],  value_left)
        pais_ciudad  = Paragraph(
            f"{factura['receptor']['pais']} / {factura['receptor']['departamento']} / {factura['receptor']['ciudad']}",
            value_left
        )
        moneda       = Paragraph(factura["documento"]["moneda"],       value_left)
        forma_pago   = Paragraph(factura["documento"]["metodo_de_pago"], value_left)
        medio_pago   = Paragraph(factura["documento"]["tipo_de_pago"], value_left)

        fecha_val = Paragraph(f"{factura['documento']['fecha']} {factura['documento']['hora']}", value_center)
        fecha_ven = Paragraph(factura["documento"]["fecha_vencimiento"],      value_center)
        email_val = Paragraph(factura["receptor"]["correo_electronico"],      value_center)

        # — Datos combinados en una sola tabla —
        data = [
            # cabeceras
            [
                Paragraph("Información del Cliente", header7), "", 
                Paragraph("Fecha y Hora de expedición", header7), 
                Paragraph("Fecha de Vencimiento",      header7)
            ],
            # Nombre + fechas
            [Paragraph("Nombre:", label_style),    nombre,    fecha_val,    fecha_ven],
            # NIT + correo (cabecera)
            [Paragraph("NIT:", label_style),       identific, Paragraph("Correo Electrónico", header7), ""],
            # Dirección + correo (valor)
            [Paragraph("Dirección:", label_style), direccion,   email_val,    ""],
            # Teléfono + Moneda
            [Paragraph("Teléfono:", label_style),  telefono,    Paragraph("Moneda:", label_style), moneda],
            # País/Dpto/Ciudad + Forma de pago
            [Paragraph("País / Dpto / Ciudad:", label_style), pais_ciudad,
            Paragraph("Forma de pago:", label_style),     forma_pago],
            # fila extra: medio de pago
            ["", "", Paragraph("Medio de pago:", label_style), medio_pago]
        ]

        colWidths = [100, 260, 98, 98]
        tbl = Table(data, colWidths=colWidths)
        tbl.setStyle(TableStyle([
            # título sección izq.
            ("SPAN",       (0, 0), (1, 0)),
            ("BACKGROUND", (0, 0), (1, 0), bg_color),
            ("TEXTCOLOR",  (0, 0), (1, 0), colors.whitesmoke),
            ("ALIGN",      (0, 0), (1, 0), "CENTER"),
            ("TOPPADDING", (0, 0), (1, 0), 4), ("BOTTOMPADDING", (0, 0), (1, 0), 4),

            # span correo
            ("SPAN",       (2, 2), (3, 2)),
            ("BACKGROUND", (2, 2), (3, 2), bg_color),
            ("TEXTCOLOR",  (2, 2), (3, 2), colors.whitesmoke),
            ("ALIGN",      (2, 2), (3, 2), "CENTER"),
            ("TOPPADDING", (2, 2), (3, 2), 2), ("BOTTOMPADDING", (2, 2), (3, 2), 2),

            # correo valor (span fila 3)
            ("SPAN",       (2, 3), (3, 3)),
            ("ALIGN",      (2, 3), (3, 3), "LEFT"),
            ("LEFTPADDING",  (2, 3), (3, 3), 2),
            ("RIGHTPADDING", (2, 3), (3, 3), 2),

            # encabezados fechas
            ("BACKGROUND", (2, 0), (3, 0), bg_color),
            ("TEXTCOLOR",  (2, 0), (3, 0), colors.whitesmoke),
            ("ALIGN",      (2, 0), (3, 0), "CENTER"),
            ("TOPPADDING", (2, 0), (3, 0), 4), ("BOTTOMPADDING", (2, 0), (3, 0), 4),

            # bordes
            ("BOX",       (0, 0), (-1, -1), 1, colors.black),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),

            # vertical align y fuente
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE",   (0, 1), (-1, -1), 7),

            # espaçamento reducido en todas las celdas (filas de datos)
            ("TOPPADDING",    (0, 1), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 0),
        ]))

        elements.append(tbl)
        elements.append(Spacer(1, 12))




    # **Tabla de Detalles de Facturación**
    def agregar_detalle_factura(detalles):
        styles = getSampleStyleSheet()
        descripcion_style = ParagraphStyle(
            name="DescripcionDetalleFactura",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=8,
            alignment=0  # Alineado a la izquierda
        )
        
        factura_detalles = [
            ["#", "Descripción", "U. Med", "Cantidad", "Valor Unitario", "% Imp.", "Descuento", "Total"]
        ]

        for detalle in detalles:
            factura_detalles.append([
                detalle["numero_linea"],
                Paragraph(detalle["descripcion"], descripcion_style),
                detalle["unidad_de_cantidad"],
                detalle["cantidad"],
                f"${float(detalle['valor_unitario']):,.2f}",
                f"{detalle['impuestos_detalle']['porcentaje_impuesto']}%",
                f"${float(detalle['cargo_descuento']['valor_cargo_descuento']):,.2f}",
                f"${float(detalle['valor_total_detalle']):,.2f}",
            ])

        detalle_table = Table(factura_detalles, colWidths=[25, 180, 40, 40, 75, 50, 75, 75])
        detalle_table.setStyle(TableStyle([
            # **Encabezado de la tabla con fondo gris y texto blanco**
            ('BACKGROUND', (0, 0), (-1, 0), color_fondo),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),

            # **Bordes NEGROS solo para las COLUMNAS (líneas verticales)**
            ('LINEBEFORE', (1, 0), (-1, -1), 1, colors.black),  # Líneas verticales en todas las columnas

            # **Bordes BLANCOS para las FILAS (líneas horizontales)**
            ('LINEABOVE', (0, 1), (-1, -1), 1, colors.white),  # Líneas blancas entre filas
            ('LINEBELOW', (0, 0), (-1, -1), 1, colors.white),  # Líneas blancas abajo

            # **Borde exterior negro grueso**
            ('BOX', (0, 0), (-1, -1), 1.5, colors.black),

            # **Alinear contenido**
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            # **Tamaño de fuente y espaciado**
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(detalle_table)
        elements.append(Spacer(1, 8))

    # **Subtotal, Descuento, IVA y Total**
    def agregar_totales():
        # — Estilos para celdas —
        styles = getSampleStyleSheet()
        normal = styles["Normal"]

        # etiquetas en fuente normal
        label_style = ParagraphStyle(
            name="LabelTotales",
            parent=normal,
            fontName="Helvetica",
            fontSize=7,
            leading=7,
            alignment=0,  # izquierda
        )
        # valores en negrita
        value_style = ParagraphStyle(
            name="ValueTotales",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=7,
            alignment=2,  # derecha
        )

        # — Color de fondo dinámico —
        bg_hex   = factura.get("caracteristicas", {}).get("color_fondo", "#004d66")
        bg_color = hex_to_rgb_color(bg_hex)

        # — Generar QR —
        qr_code = generar_qr(factura['documento']['qr'])
        qr_path = "temp_qr.png"
        with open(qr_path, "wb") as f:
            f.write(qr_code.getbuffer())
        qr_image = Image(qr_path, width=70, height=70)

        # — Subtabla Orden de Compra —
        oc_num = factura["documento"].get("numero_orden", "")
        oc_tbl = Table([
            [Paragraph("Orden de Compra", ParagraphStyle(
                name="HeaderOC",
                parent=normal,
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=9,
                textColor=colors.whitesmoke,
                alignment=1
            ))],
            [Paragraph(oc_num, ParagraphStyle(
                name="ValueOC",
                parent=normal,
                fontName="Helvetica",
                fontSize=7,
                leading=7,
                alignment=1
            ))]
        ], colWidths=[140])
        oc_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), bg_color),
            ("BOX",           (0, 0), (-1, -1), 1, colors.black),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN",         (0, 0), (-1, 1), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, 0), 2),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ]))

        # — Valores totales en Paragraphs —
        subt  = Paragraph(f"${float(factura['valores_totales']['valor_base']):,.2f}", value_style)
        desc  = Paragraph(f"${float(factura['valores_totales']['valor_descuento_total']):,.2f}", value_style)
        iva   = Paragraph(f"${float(factura['valores_totales']['valor_total_impuesto_1']):,.2f}", value_style)
        antic = Paragraph(f"${float(factura['valores_totales']['valor_anticipo']):,.2f}", value_style)
        total = Paragraph(f"${float(factura['valores_totales']['valor_total_a_pagar']):,.2f}", value_style)

        # — Tabla Totales — (2 columnas)
        totales_data = [
            [Paragraph("Subtotal:",        label_style), subt],
            [Paragraph("Descuento Global:",label_style), desc],
            [Paragraph("IVA:",             label_style), iva],
            [Paragraph("Anticipo:",        label_style), antic],
            [Paragraph("Total a Pagar:",   label_style), total],
        ]
        tot_tbl = Table(totales_data, colWidths=[100, 100])
        tot_tbl.setStyle(TableStyle([
            ("BOX",           (0, 0), (-1, -1), 1, colors.black),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 2),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
            ("TOPPADDING",    (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]))

        # — Combinar QR, OC y Totales en una sola fila —
        qr_width     = 80
        spacer_width = 110
        oc_width     = 140
        tot_width    = 556 - qr_width - spacer_width - oc_width

        combo = Table(
            [[qr_image, "", oc_tbl, tot_tbl]],
            colWidths=[qr_width, spacer_width, oc_width, tot_width]
        )
        combo.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("ALIGN",        (0, 0), (0, 0),   "LEFT"),
            ("ALIGN",        (1, 0), (1, 0),   "CENTER"),
            ("ALIGN",        (2, 0), (2, 0),   "RIGHT"),
            ("LEFTPADDING",  (1, 0), (1, 0),   30),  # corre OC hacia la derecha
            ("RIGHTPADDING", (1, 0), (1, 0),   30),
        ]))

        elements.append(combo)
        elements.append(Spacer(1, 8))


    # **Datos Adicionales del Sector Salud**
    def agregar_sector_salud():
        # **Extraer CUFE**
        cufe = factura["documento"].get("cufe", "")

        # **Estilos**
        normal_style = styles["Normal"]
        negrita_titulos = ParagraphStyle(
            name="Negrita7",
            parent=normal_style,
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.whitesmoke,
            alignment=1
        )
        valor_style = ParagraphStyle(
            name="ValorCUFE",
            parent=normal_style,
            fontName="Helvetica",
            fontSize=8,
            leading=8,
            alignment=1
        )

        # **Datos para la tabla**: solo el CUFE
        sector_data = [
            [Paragraph("CUFE / CUDE / CUNE", negrita_titulos)],    # Cabecera
            [Paragraph(cufe, valor_style)]           # Valor
        ]

        # **Construcción de la tabla**
        sector_table = Table(sector_data, colWidths=[560])  # 1 sola columna de ancho completa
        sector_table.setStyle(TableStyle([
            # Cabecera con fondo dinámico y texto blanco
            ("BACKGROUND",    (0, 0), (-1, 0), color_fondo),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
            ("FONTSIZE",      (0, 0), (-1, 0), 8),
            ("TOPPADDING",    (0, 0), (-1, 0), 4),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 4),

            # Borde exterior negro
            ("BOX",           (0, 0), (-1, -1), 1.5, colors.black),

            # Bordes internos (separador entre título y valor)
            ("LINEBELOW",     (0, 0), (-1, 0), 1, colors.white),

            # Valor centrado
            ("ALIGN",         (0, 1), (-1, 1), "CENTER"),
            ("FONTSIZE",      (0, 1), (-1, 1), 7),
            ("TOPPADDING",    (0, 1), (-1, 1), 2),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 2),
        ]))

        elements.append(sector_table)
        elements.append(Spacer(1, 8))

    def agregar_obs_documento():
        normal_style = styles["Normal"]

        negrita_titulos = ParagraphStyle(
            name="Negrita7",
            parent=normal_style,
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.whitesmoke
        )

        texto_obs = factura["otros"].get("informacion_adicional", "")
        
        # 👉 Estilo del contenido largo
        estilo_contenido = ParagraphStyle(
            name="ContenidoObservaciones",
            parent=normal_style,
            fontName="Helvetica",
            fontSize=7,
            leading=9,          # Espaciado vertical
            alignment=0,        # Izquierda
        )

        obs_data = [
            [Paragraph("<b>Observaciones Documento</b>", negrita_titulos)],
            [Paragraph(texto_obs, estilo_contenido), "", "", ""]
        ]

        obs_table = Table(obs_data, colWidths=[100, 180, 100, 180])
        obs_table.setStyle(TableStyle([
            ('SPAN', (0, 0), (-1, 0)),  # Encabezado
            ('SPAN', (0, 1), (-1, 1)),  # 👈 También fusionamos toda la fila del contenido
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, 0), color_fondo),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 1), (-1, -1), 1, colors.white),
            ('BOX', (0, 0), (-1, -1), 1.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('LEADING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
        ]))

        elements.append(obs_table)
        elements.append(Spacer(1, 8))

    agregar_encabezado()
    agregar_info_cliente()
    
    styles = getSampleStyleSheet()
    descripcion_style = ParagraphStyle(
        name="DescripcionDetalleFactura",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=8,
        alignment=0
    )

    def agregar_tabla_detalle(buffer_filas):
        if not buffer_filas:
            return

        # solo si pedimos encabezado solo en primera y estamos en página >1
        if solo_primera and page_number > 1:
            # estilo para el encabezado
            header_style = ParagraphStyle(
                name="HeaderDetalle",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                alignment=1  # centrar
            )
            encabezado_data = [[
                Paragraph("Factura electrónica de venta", header_style),
                Paragraph(factura["documento"]["identificacion"], header_style)
            ]]
            # ancho total de la tabla de detalle: 25+180+40+40+75+50+75+75 = 560
            header_tbl = Table(encabezado_data, colWidths=[400, 160])
            header_tbl.setStyle(TableStyle([
                ("BOX",           (0, 0), (-1, -1), 1, colors.black),
                ("BACKGROUND",    (0, 0), (-1, -1), colors.whitesmoke),
                ("TEXTCOLOR",     (0, 0), (-1, -1), colors.black),
                ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ]))
            elements.append(header_tbl)
            elements.append(Spacer(1, 6))

        tabla = Table(
            [["#", "Descripción", "U. Med", "Cantidad", "Valor Unitario", "% Imp.", "Descuento", "Total"]] + buffer_filas,
            colWidths=[25, 180, 40, 40, 75, 50, 75, 75]
        )
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), color_fondo),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('LINEBEFORE', (1, 0), (-1, -1), 1, colors.black),
            ('LINEABOVE', (0, 1), (-1, -1), 1, colors.white),
            ('LINEBELOW', (0, 0), (-1, -1), 1, colors.white),
            ('BOX', (0, 0), (-1, -1), 1.5, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(tabla)
        elements.append(Spacer(1, 8))

    page_number = 1
    altura_actual = header1
    buffer_filas = []

    for detalle in factura["detalles"]:
        parrafo = Paragraph(detalle["descripcion"], descripcion_style)
        altura_parrafo = parrafo.wrap(180, 0)[1]
        altura_fila = max(altura_parrafo, 5) + 4

        # elegimos el espacio disponible según si es página 1 o siguientes
        current_available = (
            avail1
            if page_number == 1
            else availN
        )

        if altura_actual + altura_fila > current_available:
            # 1) pintamos lo acumulado
            agregar_tabla_detalle(buffer_filas)

            # 2) rellenamos hasta el footer
            espacio_restante = current_available - altura_actual
            if espacio_restante > 0:
                elements.append(Spacer(1, espacio_restante))

            # 3) reset buffer y avanzar página
            if not solo_ultima_totales:
                # primero vaciamos la tabla de detalle
                agregar_totales()
                agregar_sector_salud()
            
            buffer_filas = []
            elements.append(PageBreak())
            page_number += 1
            altura_actual = headerN

            # 4) si no es solo primera, reponemos encabezado
            if not solo_primera:
                agregar_encabezado()
                agregar_info_cliente()

        # 5) acumulamos la fila
        buffer_filas.append([
            detalle["numero_linea"],
            parrafo,
            detalle["unidad_de_cantidad"],
            detalle["cantidad"],
            f"${float(detalle['valor_unitario']):,.2f}",
            f"{detalle['impuestos_detalle']['porcentaje_impuesto']}%",
            f"${float(detalle['cargo_descuento']['valor_cargo_descuento']):,.2f}",
            f"${float(detalle['valor_total_detalle']):,.2f}",
        ])
        altura_actual += altura_fila

    # pintamos lo que quede antes de totales
    agregar_tabla_detalle(buffer_filas)
    if solo_ultima_totales or not solo_ultima_totales:
        agregar_totales()
        agregar_sector_salud()
    texto_obs = factura.get("otros", {}).get("informacion_adicional", "")
    if texto_obs and texto_obs.strip():
        agregar_obs_documento()
        
    def paginas_basico(canvas, doc):
        agregar_marca_agua(canvas, factura)
        agregar_pie_pagina(canvas, doc, factura)
        agregar_autorretenedores(canvas, doc, factura)

    pdf.build(
        elements,
        onFirstPage=lambda canvas, doc: primera_pagina(canvas, doc, factura),
        onLaterPages=lambda canvas, doc: (
            paginas_basico(canvas, doc)
            if solo_primera
            else paginas_siguientes(canvas, doc, factura)
        ),
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(*args, factura=factura, **kwargs)
    )
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    hoy = datetime.now()
    pdf_filename = f"cufe_{factura['documento']['cufe']}_{hoy.strftime('%Y%m%d_%H%M%S_%f')[:-3]}.pdf"

    ruta_doc = factura["documento"].get("ruta_documento")
    if ruta_doc:
        parsed = urlparse(str(ruta_doc))
        bucket_name = parsed.netloc
        key         = parsed.path.lstrip("/")
    else:
        bucket_name = S3_BUCKET_NAME
        key = (
            f"{factura['receptor']['identificacion']}/"
            f"{hoy.year}/{hoy.month:02d}/{hoy.day:02d}/"
            f"{pdf_filename}"
        )

    return {
        "pdf_bytes": pdf_bytes,
        "bucket": bucket_name,
        "key": key,
        "filename": pdf_filename,
    }
    
def _sync_upload(pdf_bytes: bytes, bucket: str, key: str):
    print(f"[sync_upload] subiendo {len(pdf_bytes)} bytes a s3://{bucket}/{key}")
    try:
        buf = BytesIO(pdf_bytes)
        s3_client.upload_fileobj(
            buf,
            bucket,
            key,
            ExtraArgs={
                "ContentType": "application/pdf",
                "ContentDisposition": "inline",
            },
        )
        print(f"[sync_upload] ¡Subida completada! s3://{bucket}/{key}")
    except Exception as e:
        print(f"[sync_upload] ERROR al subir: {e}")
        raise

async def upload_pdf_to_s3(pdf_bytes: bytes, bucket: str, key: str):
    """
    Versión async de upload_pdf_to_s3: delega el trabajo pesado
    al thread-pool internamente, liberando el event-loop.
    """
    print(f"[upload_pdf_to_s3] llamada recibida para {bucket}/{key}")
    await run_in_threadpool(_sync_upload, pdf_bytes, bucket, key)
    print(f"[upload_pdf_to_s3] función async finalizada para {bucket}/{key}")