from datetime import datetime
from urllib.parse import urlparse
from fastapi import HTTPException
from reportlab.lib.pagesizes import letter
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
        f"Dir.: {factura['emisor']['direccion']} {factura['emisor']['ciudad']}, "
        f"Tel.: {factura['emisor']['num_celular']}, "
        f"Email: {factura['emisor']['email']} | "
        f"Web: {factura['emisor']['sitio_web']}"
        
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
    proveedor_texto = factura['afacturar']['info_pt']
    
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
    canvas.translate(15, 500)  # Posición: X desde borde izq., Y desde abajo (ajustable)
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
        page_width = letter[0]
        text_y = 30

        color_hex = self.factura.get("caracteristicas", {}).get("pie_de_pagina", {}).get("Color_texto", "#000000")
        color_rgb = hex_to_rgb_color(color_hex)

        self.setFont("Helvetica", 6)
        self.setFillColor(color_rgb)

        page_num_text = f"Página {self._pageNumber} de {total_pages}"
        self.drawRightString(page_width - 28, text_y, page_num_text)



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

        qr_code = generar_qr(factura['documento']['qr'])
        qr_buffer = BytesIO(qr_code.getvalue())
        qr_image  = Image(qr_buffer, width=80, height=80)

        factura_info = Table([
            [Paragraph(f"<b>{factura['afacturar']['titulo_superior']}</b>", normal_color_style)],
            [Paragraph(f"<b>{factura['documento']['titulo_tipo_documento']}</b>", normal_color_style)],
            [Paragraph(f"<b>{factura['documento']['identificacion']}</b>", normal_color_style)]
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
        normal_style = styles["Normal"]

        # Nuevo estilo negrita con tamaño 7
        negrita_7 = ParagraphStyle(
            name="Negrita7",
            parent=normal_style,
            fontName="Helvetica-Bold",
            fontSize=7,
            spaceAfter=0,
            textColor=colors.gray
            
        )

        negrita_titulos = ParagraphStyle(
            name="Negrita7",
            parent=normal_style,
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.whitesmoke
        )

        
        # Título principal
        color_fondo_hex = factura.get("caracteristicas", {}).get("color_fondo", "#808080")  # fallback: gris
        color_fondo_rgb = hex_to_rgb_color(color_fondo_hex)

        titulo = Table([[Paragraph("Información del Cliente o Adquirente ", negrita_titulos)]], colWidths=[560])
        titulo.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), color_fondo_rgb),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        elements.append(titulo)

        def estilo_subtabla():
            return TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
                ('LINEABOVE', (0, 0), (-1, 0), 0.5, colors.black),
                ('LINEBELOW', (0, -1), (-1, -1), 0.5, colors.black),
                ('LINEBEFORE', (0, 0), (0, -1), 0.5, colors.black),
                ('LINEAFTER', (-1, 0), (-1, -1), 0.5, colors.black),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('TOPPADDING', (0, 0), (-1, -1), 0.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),
            ])

        # Sección 1
        seccion_1 = Table([
            [Paragraph("Nombre:", negrita_7), factura["receptor"]["nombre"],
            Paragraph("Correo Electrónico:", negrita_7), factura["receptor"]["correo_electronico"]],
            [Paragraph("NIT:", negrita_7), factura["receptor"]["identificacion"],
            Paragraph("Teléfono:", negrita_7), factura["receptor"]["numero_movil"]],
            [Paragraph("Dirección:", negrita_7), factura["receptor"]["direccion"],
            Paragraph("Ciudad:", negrita_7), factura["receptor"]["ciudad"]],
            [Paragraph("Departamento:", negrita_7), factura["receptor"]["departamento"],
            Paragraph("País:", negrita_7), factura["receptor"]["pais"]],
        ], colWidths=[70, 210, 100, 180])
        seccion_1.setStyle(estilo_subtabla())
        elements.append(seccion_1)

        # Sección 2
        seccion_2 = Table([
            [Paragraph("Moneda:", negrita_7), factura["documento"]["moneda"],
            Paragraph("Método de pago:", negrita_7), factura["documento"]["metodo_de_pago"]],
            [Paragraph("Tipo de pago:", negrita_7), factura["documento"]["tipo_de_pago"],
            Paragraph("Condición de pago:", negrita_7), factura["documento"]["condicion_de_pago"]],
            [Paragraph("Orden de Compra:", negrita_7), factura["documento"]["numero_orden"], "", ""]
        ], colWidths=[100, 180, 100, 180])
        seccion_2.setStyle(estilo_subtabla())
        elements.append(seccion_2)

        # Sección 3
        seccion_3 = Table([
            [Paragraph("Fecha y Hora de expedición:", negrita_7), f"{factura['documento']['fecha']} {factura['documento']['hora']}",
            Paragraph("Fecha de Vencimiento:", negrita_7), factura["documento"]["fecha_vencimiento"]],
        ], colWidths=[120, 200, 120, 120])
        seccion_3.setStyle(estilo_subtabla())
        elements.append(seccion_3)

        # Sección 4
        seccion_4 = Table([
            [Paragraph("CUFE:", negrita_7), factura["documento"]["cufe"]]
        ], colWidths=[60, 500])
        seccion_4.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
            ('LINEABOVE', (0, 0), (-1, 0), 0.5, colors.black),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.black),
            ('LINEBEFORE', (0, 0), (0, 0), 0.5, colors.black),
            ('LINEAFTER', (-1, 0), (-1, 0), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
        ]))
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
            ('FONT',(0,0),(-1,1),'Times-Bold',10,12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(detalle_table)
        elements.append(Spacer(1, 8))

    # **Subtotal, Descuento, IVA y Total**
    def agregar_totales():
        # **Definir un nuevo estilo de párrafo más pequeño**
        estilo_resolucion = ParagraphStyle(
            name="ResolucionTexto",
            fontName="Helvetica",
            fontSize=7,
            leading=8,
            alignment=0,
        )

        # Párrafos con resolución y “son en letras”
        texto_resolucion        = Paragraph(factura["otros"]["resolucion"], estilo_resolucion)
        texto_son_valor_letras  = Paragraph(factura["documento"].get("son", ""), estilo_resolucion)

        # Valores numéricos en Paragraphs
        subt    = f"${float(factura['valores_totales']['valor_base']):,.2f}"
        desc    = f"${float(factura['valores_totales']['valor_descuento_total']):,.2f}"
        iva     = f"${float(factura['valores_totales']['valor_total_impuesto_1']):,.2f}"
        antic   = f"${float(factura['valores_totales']['valor_anticipo']):,.2f}"
        total   = f"${float(factura['valores_totales']['valor_total_a_pagar']):,.2f}"

        totales_data = [
            [texto_resolucion,       "Subtotal:",        subt],
            ["",                     "Descuento:",       desc],
            [texto_son_valor_letras,                     "IVA:",             iva],
            ["", "Anticipo:",        antic],
            ["",                     "Total a Pagar:",   total],
        ]

        # **Ajuste de anchos de columna**
        totales_table = Table(totales_data, colWidths=[420, 70, 70])

        totales_table.setStyle(TableStyle([
            # Borde exterior negro
            ('BOX',            (0, 0), (-1, -1), 1.5, colors.black),
            # Líneas internas blancas (invisibles)
            ('GRID',           (0, 0), (-1, -1), 1,   colors.white),
            # Alinear etiquetas (col 1) y valores (col 2) a la derecha
            ('ALIGN',          (1, 0), (-1, -1), 'RIGHT'),
            # Alinear columna 0 (resolución y son) a la izquierda
            ('ALIGN',          (0, 0), (0, -1),    'LEFT'),
            # Alineación vertical arriba en toda la tabla
            ('VALIGN',         (0, 0), (-1, -1), 'TOP'),
            # Texto y fondo blanco en todas las celdas
            ('TEXTCOLOR',      (0, 0), (-1, -1), colors.black),
            ('BACKGROUND',     (0, 0), (-1, -1), colors.white),
            # Padding compacto y tamaño de fuente
            ('BOTTOMPADDING',  (0, 0), (-1, -1), 1),
            ('TOPPADDING',     (0, 0), (-1, -1), 1),
            ('FONTSIZE',       (0, 0), (-1, -1), 7),
        ]))

        elements.append(totales_table)
        elements.append(Spacer(1, 8))

    # **Datos Adicionales del Sector Salud**
    def agregar_sector_salud():
        # **Extraer la colección de información adicional**
        
        normal_style = styles["Normal"]

        negrita_titulos = ParagraphStyle(
            name="Negrita7",
            parent=normal_style,
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.whitesmoke
        )
        
        datos_salud = factura["otros"]

        sector_data = [
            [Paragraph("<b>Datos Adicionales del Sector Salud</b>", negrita_titulos)],  # **Encabezado**
            [datos_salud.get("salud_1", ""), "", datos_salud.get("salud_2", ""), ""],  # Cobertura y modalidad de pago
            [datos_salud.get("salud_3", ""), "", datos_salud.get("salud_7", ""), ""],  # Código prestador y número de contrato
            [datos_salud.get("salud_4", ""), "", datos_salud.get("salud_5", ""), ""],  # Número de póliza y copago
            [datos_salud.get("salud_8", ""), "", datos_salud.get("salud_6", ""), ""],  # Cuota moderadora y periodo inicial
            [datos_salud.get("salud_9", ""), "", datos_salud.get("salud_11", ""), ""],  # Pagos compartidos y periodo facturación
            ["", "", "", ""]
        ]

        sector_table = Table(sector_data, colWidths=[100, 180, 100, 180])
        sector_table.setStyle(TableStyle([
            ('SPAN', (0, 0), (-1, 0)),  # **Fusionar el título en toda la fila**
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, 0), color_rgb),  # **Fondo gris para el título**
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 1), (-1, -1), 1, colors.white),  # **Bordes internos blancos**
            ('BOX', (0, 0), (-1, -1), 1.5, colors.black),  # **Bordes exteriores negros**
            ('FONTSIZE', (0, 0), (-1, -1), 7),  # **Tamaño de letra adecuado**
            ('LEADING', (0, 0), (-1, -1), 8),  # **Espaciado vertical reducido**
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),  # **Reduce el padding inferior**
            ('TOPPADDING', (0, 0), (-1, -1), 0),  # **Reduce el padding superior**
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