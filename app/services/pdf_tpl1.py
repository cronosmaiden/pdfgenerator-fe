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

load_dotenv()

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION")

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

def hex_to_rgb_color(hex_string: str) -> Color:
    hex_string = hex_string.lstrip("#")
    r, g, b = tuple(int(hex_string[i:i+2], 16) for i in (0, 2, 4))
    return Color(r / 255.0, g / 255.0, b / 255.0)

def agregar_marca_agua(canvas, factura):
    texto_marca = factura["documento"].get("marca_agua", "")
    if not texto_marca:
        return

    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 50)
    canvas.setFillGray(0.85, 0.4)  # Gris claro con transparencia

    # Coordenadas centrales
    width, height = canvas._pagesize
    canvas.translate(width / 2, height / 2)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, texto_marca.upper())

    canvas.restoreState()

# **Función para la dirección de contacto**
def agregar_direccion_contacto(canvas, doc, factura):
    canvas.saveState()
    direccion_texto = (
        f"Dir.: {factura['emisor']['direccion']} {factura['emisor']['ciudad']}, "
        f"Tel.: {factura['emisor']['num_celular']}, "
        f"Email: {factura['emisor']['email']} | "
        f"Web: {factura['emisor']['sitio_web']}"
        
    )
    canvas.setFont("Helvetica", 7)
    page_width = doc.pagesize[0]
    
    y = getattr(doc, "Y_DIRECCION", 65)  # 65 por defecto
    canvas.drawCentredString(page_width/2, y, direccion_texto)
    canvas.restoreState()

# **Función para los Autorretenedores**
def agregar_autorretenedores(canvas, doc, factura):
    canvas.saveState()

    # 1) Texto a mostrar
    notas_texto = factura.get("documento", {}) \
                       .get("notas_pie_pagina",
                            "Autorretenedores: Información no disponible.")

    # 2) Estilo con leading reducido (menos espacio entre líneas)
    estilo_auto = ParagraphStyle(
        name="Autorretenedores",
        fontName="Helvetica",
        fontSize=7,
        leading=7,       # antes era un simple drawString, ahora más compacto
        alignment=1,     # 0=left,1=center,2=right
        spaceBefore=0,
        spaceAfter=0,
    )

    # 3) Creamos el Paragraph para que haga wrap
    p = Paragraph(notas_texto, estilo_auto)

    # 4) Calculamos el ancho disponible según márgenes
    ancho_disponible = doc.pagesize[0] - (doc.leftMargin + doc.rightMargin)

    # 5) Ajustamos (wrap) y obtenemos la altura que ocupa
    w, h = p.wrap(ancho_disponible, doc.bottomMargin)

    # 6) Dibujamos el párrafo centrado horizontalmente, a 50pt del fondo
    x = doc.leftMargin
    y = getattr(doc, "Y_AUTORRETE", 50)   # 50 por defecto
    p.drawOn(canvas, doc.leftMargin, y)
    canvas.restoreState()

# **Función para el pie de página**
def agregar_pie_pagina(canvas, doc, factura):
    color_texto_footer_hex = factura.get("caracteristicas", {}).get("pie_de_pagina", {}).get("Color_texto", "#000000")
    color_texto_footer_rgb = hex_to_rgb_color(color_texto_footer_hex)
    canvas.saveState()
    
    # 📌 Texto del proveedor
    proveedor_texto = factura['afacturar']['info_pt']
    
    page_width = doc.pagesize[0]
    text_y = 30

    canvas.setFont("Helvetica", 6)
    
    # ✅ Usa el color que obtuvimos dinámicamente
    canvas.setFillColor(color_texto_footer_rgb)

    # Texto centrado
    canvas.drawCentredString(page_width / 2 - 40, text_y, proveedor_texto)

    # ✅ Agregar logo en el pie
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

# **Funciones para manejar encabezado y pie de página correctamente**
def primera_pagina(canvas, doc, factura):
    
    #----titulo del pdf
    titulo_pdf = f"{factura['documento']['identificacion']}@afacturar.com"
    canvas.setTitle(titulo_pdf)
    # ——— Texto arriba-derecha ———
    canvas.saveState()
    canvas.setFont("Helvetica", 6)  # tamaño pequeño
    page_width, page_height = canvas._pagesize
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
    canvas.translate(15, 500)  # Posición: X desde borde izq., Y desde abajo (ajustable)
    canvas.rotate(90)  # Rota para que el texto vaya de abajo hacia arriba
    canvas.drawString(0, 0, f"Fecha de validación DIAN: {factura['documento']['fecha_validacion_dian']}")
    canvas.restoreState()

def paginas_siguientes(canvas, doc, factura):
    
    # ——— Texto arriba-derecha ———
    canvas.saveState()
    canvas.setFont("Helvetica", 6)  # tamaño pequeño
    page_width, page_height = canvas._pagesize
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
    canvas.translate(15, 500) # Posición: X desde borde izq., Y desde abajo (ajustable)
    canvas.rotate(90)  # Rota para que el texto vaya de abajo hacia arriba
    canvas.drawString(0, 0, f"Fecha de validación DIAN: {factura['documento']['fecha_validacion_dian']}")
    canvas.restoreState()

class NumberedCanvas(canvas_module.Canvas):
    def __init__(self, *args, factura=None, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self.factura = factura
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))  # Guarda el estado
        self._startPage()  # Prepara una nueva página sin dibujar aún

    def save(self):
        total_pages = len(self._saved_page_states)

        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(total_pages)
            super(NumberedCanvas, self).showPage()

        super(NumberedCanvas, self).save()

    def draw_page_number(self, total_pages):
        page_width = self._pagesize[0]
        text_y = 30

        color_hex = self.factura.get("caracteristicas", {}).get("pie_de_pagina", {}).get("Color_texto", "#000000")
        color_rgb = hex_to_rgb_color(color_hex)

        self.setFont("Helvetica", 6)
        self.setFillColor(color_rgb)

        page_num_text = f"Página {self._pageNumber} de {total_pages}"
        self.drawRightString(page_width - 28, text_y, page_num_text)



def generar_pdf(factura):
    
    papel = factura.get("caracteristicas", {}).get("papel", "letter").upper()
    try:
        page_size = getattr(pagesizes, papel)
    except AttributeError:
        papel = "LETTER"
        page_size = pagesizes.LETTER

    # Ancho y alto de la hoja
    page_width, page_height = page_size

    # Obtén los parámetros para este papel (o los de LETTER si no existe)
    params = PAGE_PARAMS.get(papel, PAGE_PARAMS["LETTER"])
    header_height_first = params["header_height_first"]
    header_height_later = params["header_height_later"]
    footer_height      = params["footer_height"]
    
    # Construye el SimpleDocTemplate
    buffer = BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=28,
        rightMargin=28,
        topMargin=28,
        bottomMargin=28,
    )

    pdf.Y_NOTAS     = params["Y_NOTAS"]
    pdf.Y_DIRECCION = params["Y_DIRECCION"]
    pdf.Y_AUTORRETE = params["Y_AUTORRETE"]

    # Flags de configuración
    solo_primera = (
        factura.get("caracteristicas", {})
               .get("encabezado", {})
               .get("solo_primera_pagina", 0)
        == 1
    )
    show_totales_last_only = (
        factura.get("caracteristicas", {})
               .get("totales", {})
               .get("solo_ultima_pagina", 1)
        == 1
    )

    # Altura del bloque de totales (fija)
    totales_height = 105

    # Márgenes
    top_margin    = pdf.topMargin
    bottom_margin = pdf.bottomMargin

    # Espacio disponible “crudo” antes de restar totales
    base_available_first = (
        page_height
        - top_margin
        - bottom_margin
        - header_height_first
        - footer_height
    )
    base_available_later = (
        page_height
        - top_margin
        - bottom_margin
        - header_height_later
        - footer_height
    )

    # Si sólo mostramos totales en la última, no restamos su altura
    if show_totales_last_only:
        available_height_first = base_available_first
        available_height_later = base_available_later
    else:
        # En todas las páginas restamos además el bloque de totales
        available_height_first = base_available_first - totales_height
        available_height_later = base_available_later - totales_height


    styles = getSampleStyleSheet()
    elements = []

    color_hex = factura.get("caracteristicas", {}).get("color_fondo", "#808080")
    color_rgb = hex_to_rgb_color(color_hex)

    color_texto_encabezado_hex = factura.get("caracteristicas", {}).get("encabezado", {}).get("Color_texto", "#000000")
    color_texto_encabezado_rgb = hex_to_rgb_color(color_texto_encabezado_hex)

    

    # **Encabezado Principal**
    def agregar_encabezado():
        razon_social_style = ParagraphStyle(
            name="RazonSocialTitle",
            fontName="Helvetica-Bold",
            fontSize=12,
            alignment=1,
            textColor=color_texto_encabezado_rgb,
            spaceAfter=6
        )

        normal_color_style = ParagraphStyle(
            name="EncabezadoColorTexto",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            textColor=color_texto_encabezado_rgb
        )
        centered_bold_7 = ParagraphStyle(
            name="CenteredBold7",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            textColor=color_texto_encabezado_rgb,
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

        qr_code = generar_qr(factura['documento']['qr'])
        qr_buffer = BytesIO(qr_code.getvalue())
        qr_image  = Image(qr_buffer, width=80, height=80)

        factura_info = Table([
            [Paragraph(f"<b>{factura['documento']['titulo_tipo_documento']}</b>", centered_bold_7)],
            [Paragraph(f"<b>{factura['documento']['identificacion']}</b>", centered_bold_7)]
        ], colWidths=[110])
        factura_info.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))

        header_row = Table([
            [[logo_ofe_img] if logo_ofe_img else [""],info_paragraphs, qr_image, factura_info]
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

        # estilo para las "etiquetas" (Nombre:, Correo:, etc.) — fuente normal
        label_style = ParagraphStyle(
            name="LabelStyle",
            parent=normal,
            fontName="Helvetica",
            fontSize=7,
            leading=8,
            textColor=colors.black,
        )

        # estilo para los "valores" — negrita
        value_style = ParagraphStyle(
            name="ValueStyle",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=8,
            textColor=colors.black,
        )

        negrita_titulos = ParagraphStyle(
            name="Negrita7",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=7,
            spaceBefore=1,
            spaceAfter=1,
            textColor=colors.whitesmoke
        )

        # Título de sección
        color_fondo_hex = factura.get("caracteristicas", {}).get("color_fondo", "#808080")
        color_fondo_rgb = hex_to_rgb_color(color_fondo_hex)

        titulo = Table([[Paragraph("Información del Cliente o Adquirente", negrita_titulos)]], colWidths=[560])
        titulo.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), color_fondo_rgb),
            ("TEXTCOLOR",    (0, 0), (-1, -1), colors.whitesmoke),
            ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
            ("BOX",          (0, 0), (-1, -1), 1, colors.black),
            ("FONTSIZE",     (0, 0), (-1, -1), 7),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ]))
        elements.append(titulo)

        # estilo común de bordes y espaciado
        common_table_style = TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("BOX",         (0, 0), (-1, -1), 1, colors.black),
            ("LINEABOVE",   (0, 0), (-1, 0), 0.5, colors.black),
            ("LINEBELOW",   (0, -1),(-1, -1),0.5, colors.black),
            ("LINEBEFORE",  (0, 0), (0, -1), 0.5, colors.black),
            ("LINEAFTER",   (-1, 0),(-1, -1),0.5, colors.black),
            ("FONTSIZE",    (0, 0), (-1, -1), 7),
            ("TOPPADDING",  (0, 0), (-1, -1), 0.5),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 0.5),
        ])

        # Sección 1: Nombre y Correo en filas independientes
        seccion_1 = Table([
            [Paragraph("Nombre:",        label_style), factura["receptor"]["nombre"],              "", ""],
            [Paragraph("NIT:",           label_style), factura["receptor"]["identificacion"],     Paragraph("Teléfono:", label_style), factura["receptor"]["numero_movil"]],
            [Paragraph("Correo Electrónico:", label_style), factura["receptor"]["correo_electronico"], "", ""],
            [Paragraph("Dirección:",     label_style), factura["receptor"]["direccion"],          Paragraph("Ciudad:",    label_style), factura["receptor"]["ciudad"]],
            [Paragraph("Departamento:",  label_style), factura["receptor"]["departamento"],       Paragraph("País:",      label_style), factura["receptor"]["pais"]],
        ], colWidths=[100, 220, 100, 140])
        # convertimos los valores a Paragraph con estilo bold
        for row in seccion_1._cellvalues:
            # celdas índice 1 y 3 (si existen) son valores
            for idx in (1, 3):
                if isinstance(row[idx], str):
                    row[idx] = Paragraph(row[idx], value_style)

        common_cmds = common_table_style._cmds
        style_s1 = TableStyle(common_cmds + [
            ('SPAN', (1, 0), (3, 0)),  # extiende la celda de nombre desde la columna 1 hasta la 3
            ('SPAN', (1, 2), (3, 2)), # extiende la celda de Correo Electrónico desde la columna 1 hasta la 3
        ])

        seccion_1.setStyle(style_s1)
        elements.append(seccion_1)

        # Sección 2: Datos de pago
        seccion_2 = Table([
            [Paragraph("Moneda:",       label_style), Paragraph(factura["documento"]["moneda"], value_style),
            Paragraph("Método de pago:",label_style), Paragraph(factura["documento"]["metodo_de_pago"], value_style)],
            [Paragraph("Tipo de pago:", label_style), Paragraph(factura["documento"]["tipo_de_pago"], value_style),
            Paragraph("Orden de Compra:", label_style), Paragraph(factura["documento"]["numero_orden"], value_style)],
        ], colWidths=[100, 180, 100, 180])
        seccion_2.setStyle(common_table_style)
        elements.append(seccion_2)

        # Sección 3: Fechas
        seccion_3 = Table([
            [Paragraph("Fecha y Hora de expedición:", label_style),
            Paragraph(f"{factura['documento']['fecha']} {factura['documento']['hora']}", value_style),
            Paragraph("Fecha de Vencimiento:", label_style),
            Paragraph(factura["documento"]["fecha_vencimiento"], value_style)],
        ], colWidths=[120, 200, 120, 120])
        seccion_3.setStyle(common_table_style)
        elements.append(seccion_3)

        # Sección 4: CUFE
        seccion_4 = Table([
            [Paragraph("CUFE:", label_style), Paragraph(factura["documento"]["cufe"], value_style)]
        ], colWidths=[60, 500])
        seccion_4.setStyle(common_table_style)
        elements.append(seccion_4)

        elements.append(Spacer(1, 8))



    # **Tabla de Detalles de Facturación**
    def agregar_detalle_factura(detalles):
        styles = getSampleStyleSheet()
        descripcion_style = ParagraphStyle(
            name="DescripcionDetalleFactura",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=6,
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
            ('BACKGROUND', (0, 0), (-1, 0), color_rgb),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),

            # **Bordes NEGROS solo para las COLUMNAS (líneas verticales)**
            ('LINEBEFORE', (1, 0), (-1, -1), 1, colors.black),  # Líneas verticales en todas las columnas

            # **Bordes BLANCOS para las FILAS (líneas horizontales)**
            ('LINEABOVE', (0, 1), (-1, -1), 1, colors.white),  # Líneas blancas entre filas
            ('LINEBELOW', (0, 0), (-1, -1), 1, colors.white),  # Líneas blancas abajo

            # **Borde exterior negro grueso**
            ('BOX', (0, 0), (-1, -1), 1, colors.black),

            # **Alinear contenido**
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            # **Tamaño de fuente y espaciado**
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('FONT',(0,0),(-1,1),'Times-Bold',10,12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
        ]))
        elements.append(detalle_table)
        elements.append(Spacer(1, 8))

    # **Subtotal, Descuento, IVA y Total**
    def agregar_totales():
        styles = getSampleStyleSheet()

        # Reducimos el leading para apretar filas
        estilo_resolucion = ParagraphStyle(
            name="ResolucionTexto",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=6,     
            alignment=0,
        )
        label_style = ParagraphStyle(
            name="Label7",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=6,      
            textColor=colors.black,
            alignment=2,
        )
        value_style = ParagraphStyle(
            name="ValueBold7",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=6,    
            textColor=colors.black,
            alignment=2,
        )

        # Párrafos
        texto_resolucion       = Paragraph(factura["otros"]["resolucion"], estilo_resolucion)
        texto_son_valor_letras = Paragraph(factura["documento"].get("son", ""), estilo_resolucion)

        subt  = f"${float(factura['valores_totales']['valor_base']):,.2f}"
        desc  = f"${float(factura['valores_totales']['valor_descuento_total']):,.2f}"
        iva   = f"${float(factura['valores_totales']['valor_total_impuesto_1']):,.2f}"
        antic = f"${float(factura['valores_totales']['valor_anticipo']):,.2f}"
        total = f"${float(factura['valores_totales']['valor_total_a_pagar']):,.2f}"

        totales_data = [
            [texto_resolucion, "", Paragraph("Subtotal:", label_style), Paragraph(subt,  value_style)],
            ["",               "", Paragraph("Descuento:", label_style), Paragraph(desc,  value_style)],
            [texto_son_valor_letras, "", Paragraph("IVA:", label_style), Paragraph(iva,   value_style)],
            ["",               "", Paragraph("Anticipo:", label_style), Paragraph(antic, value_style)],
            ["",               "", Paragraph("Total a Pagar:", label_style), Paragraph(total, value_style)],
        ]

        totales_table = Table(totales_data, colWidths=[420, 0, 70, 70])
        style = TableStyle([
            ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX',         (0, 0), (-1, -1),  1, colors.black),
            ('LINEABOVE',   (0, 0), (-1, 0),    0.5, colors.black),
            ('LINEBELOW',   (0, -1),(-1, -1),   0.5, colors.black),
            ('LINEBEFORE',  (0, 0), (0, -1),    0.5, colors.black),
            ('LINEAFTER',   (-1, 0),(-1, -1),   0.5, colors.black),
            ('TOPPADDING',  (0, 0), (-1, -1),   0),
            ('BOTTOMPADDING',(0, 0), (-1, -1),   0),
        ])
        totales_table.setStyle(style)

        elements.append(totales_table)
        elements.append(Spacer(1, 8))


    # **Datos Adicionales del Sector Salud**
    def agregar_sector_salud():
        # Estilos base
        normal_style = styles["Normal"]
        # Label en normal
        label_style = ParagraphStyle(
            name="SectorLabel",
            parent=normal_style,
            fontName="Helvetica",
            fontSize=7,
            leading=8,
            textColor=colors.black,
        )
        # Valor en negrita
        value_style = ParagraphStyle(
            name="SectorValue",
            parent=normal_style,
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=8,
            textColor=colors.black,
        )

        datos_salud = factura["otros"]

        # Datos crudos
        raw = [
            [f"<b>Datos Adicionales del Sector Salud</b>", "", "", ""],
            [datos_salud.get("salud_1", ""), "", datos_salud.get("salud_2", ""), ""],
            [datos_salud.get("salud_3", ""), "", datos_salud.get("salud_7", ""), ""],
            [datos_salud.get("salud_4", ""), "", datos_salud.get("salud_5", ""), ""],
            [datos_salud.get("salud_8", ""), "", datos_salud.get("salud_6", ""), ""],
            [datos_salud.get("salud_9", ""), "", datos_salud.get("salud_10", ""), ""],
            ["", "", "", ""],
        ]

        # Convertimos a Paragraph aplicando estilos
        sector_data = []
        for row_idx, row in enumerate(raw):
            new_row = []
            for col_idx, cell in enumerate(row):
                text = cell or ""
                if row_idx == 0:
                    # Título en negrita blanca
                    new_row.append(Paragraph(text, ParagraphStyle(
                        name="TitleSector",
                        parent=normal_style,
                        fontName="Helvetica-Bold",
                        fontSize=8,
                        textColor=colors.whitesmoke
                    )))
                else:
                    # pares: cols 0 y 2 = label_style, cols 1 y 3 = value_style
                    style = label_style if col_idx in (0,2) else value_style
                    new_row.append(Paragraph(text, style))
            sector_data.append(new_row)

        # Construcción y estilo de la tabla
        sector_table = Table(sector_data, colWidths=[150, 150, 160, 100])
        sector_table.setStyle(TableStyle([
            ('SPAN', (0, 0), (-1, 0)),  # **Fusionar el título en toda la fila**
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, 0), color_rgb),  # **Fondo gris para el título**
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 1), (-1, -1), 1, colors.white),  # **Bordes internos blancos**
            ('BOX', (0, 0), (-1, -1), 1, colors.black),  # **Bordes exteriores negros**
            ('FONTSIZE', (0, 0), (-1, -1), 7),  # **Tamaño de letra adecuado**
            ('LEADING', (0, 0), (-1, -1), 8),  # **Espaciado vertical reducido**
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),  # **Reduce el padding inferior**
            ('TOPPADDING', (0, 0), (-1, -1), 0.5),  # **Reduce el padding superior**
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
            ('BACKGROUND', (0, 0), (-1, 0), color_rgb),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 1), (-1, -1), 1, colors.white),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('LEADING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
        ]))

        elements.append(obs_table)
        elements.append(Spacer(1, 8))

    def agregar_notas_adicionales():
        # **Extraer notas_adicionales**
        notas_texto = factura["documento"].get("notas_adicionales", "")
        styles = getSampleStyleSheet()
        color_fondo = hex_to_rgb_color(factura.get("caracteristicas", {}).get("color_fondo","#808080"))

        negrita_titulos = ParagraphStyle(
            name="Negrita7",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.whitesmoke,            
        )
        valor_style = ParagraphStyle(
            name="ValorTextoAdicional",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=8,
        )

        notas_data = [
            [Paragraph("Notas adicionales", negrita_titulos)],    # Cabecera
            [Paragraph(notas_texto, valor_style)]                # Valor
        ]

        notas_table = Table(notas_data, colWidths=[560])
        notas_table.setStyle(TableStyle([
            # — Título fila —
            ('SPAN',           (0, 0), (-1, 0)),
            ('BACKGROUND',     (0, 0), (-1, 0), color_fondo),
            ('TEXTCOLOR',      (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',          (0, 0), (-1, 0), 'CENTER'),
            ('FONTSIZE',       (0, 0), (-1, 0), 7),     
            ('LEADING',        (0, 0), (-1, 0), 8),     
            ('TOPPADDING',     (0, 0), (-1, 0), 0.5),   
            ('BOTTOMPADDING',  (0, 0), (-1, 0), 0.5),
            ('BOX',            (0, 0), (-1, -1), 1, colors.black),
        ]))

        elements.append(notas_table)
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
                Paragraph(factura["documento"]["titulo_tipo_documento"], header_style),
                Paragraph(factura["documento"]["identificacion"], header_style)
            ]]
            # ancho total de la tabla de detalle: 25+180+40+40+75+50+75+75 = 560
            header_tbl = Table(encabezado_data, colWidths=[400, 160])
            header_tbl.setStyle(TableStyle([
                ("BOX",           (0, 0), (-1, -1), 1, colors.black),
                ("BACKGROUND",    (0, 0), (-1, -1), colors.whitesmoke),
                ("TEXTCOLOR",     (0, 0), (-1, -1), colors.black),
                ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
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
            ('BACKGROUND', (0, 0), (-1, 0), color_rgb),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('LINEBEFORE', (1, 0), (-1, -1), 1, colors.black),
            ('LINEABOVE', (0, 1), (-1, -1), 1, colors.white),
            ('LINEBELOW', (0, 0), (-1, -1), 1, colors.white),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(tabla)
        elements.append(Spacer(1, 8))

    page_number = 1
    altura_actual = header_height_first
    buffer_filas = []

    for detalle in factura["detalles"]:
        parrafo = Paragraph(detalle["descripcion"], descripcion_style)
        altura_parrafo = parrafo.wrap(180, 0)[1]
        altura_fila = max(altura_parrafo, 10) + 4

        # elegimos el espacio disponible según si es página 1 o siguientes
        current_available = (
            available_height_first
            if page_number == 1
            else available_height_later
        )

        if altura_actual + altura_fila > current_available:
            # 1) pintamos lo acumulado
            agregar_tabla_detalle(buffer_filas)

            # 2) rellenamos hasta el footer
            espacio_restante = current_available - altura_actual
            if espacio_restante > 0:
                elements.append(Spacer(1, espacio_restante))

            # 3) reset buffer y avanzar página
            if not show_totales_last_only:
                # primero vaciamos la tabla de detalle
                agregar_totales()
                agregar_sector_salud()
                agregar_notas_adicionales()
            
            buffer_filas = []
            elements.append(PageBreak())
            page_number += 1
            altura_actual = header_height_later

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
    if show_totales_last_only or not show_totales_last_only:
        agregar_totales()
        agregar_sector_salud()
        agregar_notas_adicionales()
    texto_obs = factura.get("otros", {}).get("informacion_adicional", "")
    if texto_obs and texto_obs.strip():
        agregar_obs_documento()
        

    def paginas_basico(canvas, doc):
        agregar_marca_agua(canvas, factura)
        agregar_pie_pagina(canvas, doc, factura)
        agregar_autorretenedores(canvas, doc, factura)

    pdf.build(
        elements,
        onFirstPage=lambda c, d: primera_pagina(c, d, factura),
        onLaterPages=lambda c, d: (
            paginas_basico(c, d)
            if solo_primera
            else paginas_siguientes(c, d, factura)
        ),
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(*args, factura=factura, **kwargs),
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