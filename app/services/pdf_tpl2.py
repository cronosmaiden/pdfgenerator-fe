from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.colors import Color
from io import BytesIO
from reportlab.lib.utils import ImageReader
import boto3
import base64
import os
from app.services.qr_generator import generar_qr
from reportlab.pdfgen import canvas as canvas_module
from dotenv import load_dotenv

load_dotenv()

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
        page_width = letter[0]
        text_y = 30

        color_hex = self.factura.get("caracteristicas", {}).get("pie_de_pagina", {}).get("Color_texto", "#000000")
        color_rgb = hex_to_rgb_color(color_hex)

        self.setFont("Helvetica", 6)
        self.setFillColor(color_rgb)

        page_num_text = f"Página {self._pageNumber} de {total_pages}"
        self.drawRightString(page_width - 28, text_y, page_num_text)

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION")

s3_client = boto3.client(
    "s3",
    region_name=S3_REGION
)

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
    width, height = letter
    canvas.translate(width / 2, height / 2)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, texto_marca.upper())

    canvas.restoreState()

# **Función para la dirección de contacto**
def agregar_direccion_contacto(canvas, doc, factura):
    canvas.saveState()
    direccion_texto = (
        f"Dir.: {factura['receptor']['direccion']} {factura['receptor']['ciudad']}, "
        f"Tel.: {factura['receptor']['numero_movil']}, "
        f"Email: {factura['receptor']['correo_electronico']}"
    )
    canvas.setFont("Helvetica", 7)
    page_width = letter[0]
    
    # 🔽 Ajuste: más abajo
    canvas.drawCentredString(page_width / 2, 65, direccion_texto)
    
    canvas.restoreState()

# **Función para los Autorretenedores**
def agregar_autorretenedores(canvas, doc, factura):
    canvas.saveState()
    notas_texto = factura.get("documento", {}).get(
        "notas_pie_pagina", "Autorretenedores: Información no disponible."
    )
    canvas.setFont("Helvetica", 7)
    page_width = letter[0]

    # 🔽 Ajuste: justo encima del pie de página
    canvas.drawCentredString(page_width / 2, 50, notas_texto)
    
    canvas.restoreState()

# **Función para el pie de página**
def agregar_pie_pagina(canvas, doc, factura):
    color_texto_footer_hex = factura.get("caracteristicas", {}).get("pie_de_pagina", {}).get("Color_texto", "#000000")
    color_texto_footer_rgb = hex_to_rgb_color(color_texto_footer_hex)
    canvas.saveState()
    
    # 📌 Texto del proveedor
    proveedor_texto = "Proveedor Tecnológico: Teleinte SAS - NIT: 830.020.470-5 / Nombre del software: Afacturar.com www.afacturar.com"
    
    page_width = letter[0]
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
    agregar_marca_agua(canvas, factura)
    agregar_direccion_contacto(canvas, doc, factura)
    agregar_autorretenedores(canvas, doc, factura)
    agregar_pie_pagina(canvas, doc, factura)
    

    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(colors.grey)
    canvas.translate(15, 600)  # Posición: X desde borde izq., Y desde abajo (ajustable)
    canvas.rotate(90)  # Rota para que el texto vaya de abajo hacia arriba
    canvas.drawString(0, 0, f"Fecha de validación DIAN: {factura['documento']['fecha_validacion_dian']}")
    canvas.restoreState()

def paginas_siguientes(canvas, doc, factura):
    agregar_marca_agua(canvas, factura)
    agregar_direccion_contacto(canvas, doc, factura)
    agregar_autorretenedores(canvas, doc, factura)
    agregar_pie_pagina(canvas, doc, factura)

    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(colors.grey)
    canvas.translate(15, 600) # Posición: X desde borde izq., Y desde abajo (ajustable)
    canvas.rotate(90)  # Rota para que el texto vaya de abajo hacia arriba
    canvas.drawString(0, 0, f"Fecha de validación DIAN: {factura['documento']['fecha_validacion_dian']}")
    canvas.restoreState()

def generar_pdf(factura):
    buffer = BytesIO()
    pdf = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        leftMargin=28,  
        rightMargin=28,  
        topMargin=28,  
        bottomMargin=28  
    )

    solo_primera = (
        factura
        .get("caracteristicas", {})
        .get("encabezado", {})
        .get("solo_primera_pagina", 0)
        == 1
    )

    show_totales_last_only = factura.get("caracteristicas", {}) \
        .get("totales", {}) \
        .get("solo_ultima_pagina", 1) == 1
    
    totales_height = 105

    if solo_primera and not show_totales_last_only:
        header_height_first = 180
        header_height_later  = 90
    else:
        header_height_first = 180 if solo_primera else 180
        header_height_later  = 120   if solo_primera else 180

    page_height   = letter[1]
    top_margin    = pdf.topMargin
    bottom_margin = pdf.bottomMargin
    footer_height = 80

    base_available_first = page_height - top_margin - bottom_margin - header_height_first - footer_height
    base_available_later  = page_height - top_margin - bottom_margin - header_height_later  - footer_height

    if show_totales_last_only:
        # si solo en última hoja, usamos el espacio completo en todas
        available_height_first = base_available_first
        available_height_later  = base_available_later
    else:
        # si en todas las hojas, restamos además el espacio de totales
        available_height_first = base_available_first - totales_height
        available_height_later  = base_available_later  - totales_height

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
            fontSize=16,
            alignment=1,
            textColor=color_texto_encabezado_rgb,
            spaceAfter=6
        )

        normal_color_style = ParagraphStyle(
            name="EncabezadoColorTexto",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            textColor=color_texto_encabezado_rgb  # 👈 Nuevo
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
            [Paragraph("<b>Factura electrónica de venta</b>", normal_color_style)],
            [Paragraph(f"<b>{factura['documento']['identificacion']}</b>", normal_color_style)]
        ], colWidths=[120])
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
        label = ParagraphStyle(
            name="Label", parent=normal,
            fontName="Helvetica-Bold", fontSize=7, leading=9,
            textColor=colors.black,
            alignment=0  # izq
        )
        header7 = ParagraphStyle(
            name="Header7", parent=normal,
            fontName="Helvetica-Bold", fontSize=7, leading=9,
            textColor=colors.whitesmoke, alignment=1
        )
        value_left = ParagraphStyle(
            name="ValueLeft", parent=normal,
            fontName="Helvetica", fontSize=7, leading=9,
            textColor=colors.black, alignment=0
        )
        value_center = ParagraphStyle(
            name="ValueCenter", parent=normal,
            fontName="Helvetica", fontSize=7, leading=9,
            textColor=colors.black, alignment=1
        )

        # — Color de fondo dinámico —
        bg_hex   = factura.get("caracteristicas", {}).get("color_fondo", "#004d66")
        bg_color = hex_to_rgb_color(bg_hex)

        # — Valores párrafos (para forzar wrap) —
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
            [Paragraph("Nombre:", label),    nombre,    fecha_val,    fecha_ven],
            # NIT + correo (cabecera)
            [Paragraph("NIT:", label),       identific, Paragraph("Correo Electrónico", header7), ""],
            # Dirección + correo (valor)
            [Paragraph("Dirección:", label), direccion,   email_val,    ""],
            # Teléfono + Moneda
            [Paragraph("Teléfono:", label),  telefono,    Paragraph("Moneda:", label), moneda],
            # País/Dpto/Ciudad + Forma de pago
            [Paragraph("País / Dpto / Ciudad:", label), pais_ciudad,
            Paragraph("Forma de pago:", label),     forma_pago],
            # fila extra: medio de pago
            ["", "", Paragraph("Medio de pago:", label), medio_pago]
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
            ("SPAN",       (2, 3), (3, 3)),
            ("BACKGROUND", (2, 2), (3, 2), bg_color),
            ("TEXTCOLOR",  (2, 2), (3, 2), colors.whitesmoke),
            ("ALIGN",      (2, 2), (3, 2), "CENTER"),
            ("TOPPADDING", (2, 2), (3, 2), 2), ("BOTTOMPADDING", (2, 2), (3, 2), 2),
            ("ALIGN",      (2, 3), (3, 3), "LEFT"),
            ("LEFTPADDING",  (2, 3), (3, 3), 2),
            ("RIGHTPADDING", (2, 3), (3, 3), 2),

            # encabezados fechas
            ("BACKGROUND", (2, 0), (3, 0), bg_color),
            ("TEXTCOLOR",  (2, 0), (3, 0), colors.whitesmoke),
            ("ALIGN",      (2, 0), (3, 0), "CENTER"),
            ("TOPPADDING", (2, 0), (3, 0), 4), ("BOTTOMPADDING", (2, 0), (3, 0), 4),

            # bordes
            ("BOX",        (0, 0), (-1, -1), 0.5, colors.black),
            ("GRID",       (0, 1), (-1, -1), 0.25, colors.white),

            # alineación vertical y fuente
            ("VALIGN",     (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE",   (0, 1), (-1, -1), 7),
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
            ('BACKGROUND', (0, 0), (-1, 0), color_rgb),
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
        label = ParagraphStyle(
            name="LabelTotales", parent=styles["Normal"],
            fontName="Helvetica-Bold", fontSize=7, leading=9, alignment=0
        )
        value = ParagraphStyle(
            name="ValueTotales", parent=styles["Normal"],
            fontName="Helvetica", fontSize=7, leading=9, alignment=2
        )
        # Estilo para Orden de Compra
        header_oc = ParagraphStyle(
            name="HeaderOC", parent=styles["Normal"],
            fontName="Helvetica-Bold", fontSize=8, leading=10,
            textColor=colors.whitesmoke, alignment=1
        )
        value_oc = ParagraphStyle(
            name="ValueOC", parent=styles["Normal"],
            fontName="Helvetica", fontSize=7, leading=9, alignment=1
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
            [Paragraph("Orden de Compra", header_oc)],
            [Paragraph(oc_num, value_oc)]
        ], colWidths=[140])
        oc_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), bg_color),
            ("BOX",           (0, 0), (-1, -1), 0.5, colors.black),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
            ("ALIGN",         (0, 1), (-1, 1), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
            ("TOPPADDING",    (0, 0), (-1, 0), 4),
        ]))

        # — Valores totales en Paragraphs —
        subt  = Paragraph(f"${float(factura['valores_totales']['valor_base']):,.2f}", value)
        desc  = Paragraph(f"${float(factura['valores_totales']['valor_descuento_total']):,.2f}", value)
        iva   = Paragraph(f"${float(factura['valores_totales']['valor_total_impuesto_1']):,.2f}", value)
        antic = Paragraph(f"${float(factura['valores_totales']['valor_anticipo']):,.2f}", value)
        total = Paragraph(f"${float(factura['valores_totales']['valor_total_a_pagar']):,.2f}", value)

        # Estilo especial para "Total a Pagar"
        label_total = ParagraphStyle(
            name="LabelTotalPagar", parent=label,
            fontSize=8
        )

        # — Tabla Totales — (siempre 2 columnas)
        totales_data = [
            [Paragraph("Subtotal:",         label), subt],
            [Paragraph("Descuento Global:", label), desc],
            [Paragraph("IVA:",              label), iva],
            [Paragraph("Anticipo:",         label), antic],
            [Paragraph("Total a Pagar:",    label_total), total]
        ]
        tot_tbl = Table(totales_data, colWidths=[100, 100])
        tot_tbl.setStyle(TableStyle([
            ("BOX",           (0, 0), (-1, -1), 0.5, colors.black),
            ("GRID",          (0, 0), (-1, -1), 0.25, colors.white),
            ("ALIGN",         (0, 0), (0, -1), "LEFT"),
            ("ALIGN",         (1, 0), (1, -1), "RIGHT"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE",      (0, 0), (-1, -1), 7),
            ("LEFTPADDING",   (0, 0), (-1, -1), 2),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))

        # — Combinar QR, OC y Totales en una sola fila —
        qr_width     = 80
        spacer_width = 110
        oc_width     = 120
        tot_width    = 556 - qr_width - spacer_width - oc_width

        combo = Table(
            [[qr_image, "", oc_tbl, tot_tbl]],
            colWidths=[qr_width, spacer_width, oc_width, tot_width]
        )
        combo.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("ALIGN",        (0, 0), (0, 0), "LEFT"),
            ("ALIGN",        (1, 0), (1, 0), "CENTER"),
            ("ALIGN",        (2, 0), (2, 0), "RIGHT"),
            ("LEFTPADDING",  (1, 0), (1, 0), 30),  # correr OC hacia la derecha
            ("RIGHTPADDING", (1, 0), (1, 0), 30),
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
            fontSize=7,
            leading=8,
            alignment=1
        )

        # **Datos para la tabla**: solo el CUFE
        sector_data = [
            [Paragraph("CUFE", negrita_titulos)],    # Cabecera
            [Paragraph(cufe, valor_style)]           # Valor
        ]

        # **Construcción de la tabla**
        sector_table = Table(sector_data, colWidths=[560])  # 1 sola columna de ancho completa
        sector_table.setStyle(TableStyle([
            # Cabecera con fondo dinámico y texto blanco
            ("BACKGROUND",    (0, 0), (-1, 0), color_rgb),
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
            ('BACKGROUND', (0, 0), (-1, 0), color_rgb),
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
    altura_actual = header_height_first
    buffer_filas = []

    for detalle in factura["detalles"]:
        parrafo = Paragraph(detalle["descripcion"], descripcion_style)
        altura_parrafo = parrafo.wrap(180, 0)[1]
        altura_fila = max(altura_parrafo, 5) + 4

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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"cufe_{factura['documento']['cufe']}_{timestamp}.pdf"

    # 🗓️ Obtener fecha actual
    fecha_actual = datetime.now()
    anio = str(fecha_actual.year)
    mes = f"{fecha_actual.month:02d}"
    dia = f"{fecha_actual.day:02d}"

    # 📂 NIT de la empresa
    nit = factura["receptor"]["identificacion"]

    # 🛣️ Ruta dentro del bucket
    ruta_s3 = f"{nit}/{anio}/{mes}/{dia}/{pdf_filename}"

    s3_client.upload_fileobj(buffer, S3_BUCKET_NAME, ruta_s3)

    return f"{nit}/{anio}/{mes}/{dia}/{pdf_filename}"