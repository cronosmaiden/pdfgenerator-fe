from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
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
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
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
        self.setFont("Helvetica", 6)
        page_num_text = f"Página {self._pageNumber} de {total_pages}"
        self.drawRightString(page_width - 28, text_y, page_num_text)

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION")

s3_client = boto3.client(
    "s3",
    region_name=S3_REGION
)

# **Función para la dirección de contacto**
# **Función para la dirección de contacto**
def agregar_direccion_contacto(canvas, doc, factura):
    canvas.saveState()
    direccion_texto = (
        f"Dir.: {factura['datos_obligado']['direccion']} {factura['datos_obligado']['depto_ciudad']}, "
        f"Tel.: {factura['datos_obligado']['telefono']}, "
        f"Email: {factura['datos_obligado']['email']}"
    )
    canvas.setFont("Helvetica", 7)
    page_width = letter[0]
    
    # 🔽 Ajuste: más abajo
    canvas.drawCentredString(page_width / 2, 65, direccion_texto)
    
    canvas.restoreState()

# **Función para los Autorretenedores**
def agregar_autorretenedores(canvas, doc, factura):
    canvas.saveState()
    notas_texto = factura.get("datos_adicionales", {}).get(
        "notas_pie_pagina", "Autorretenedores: Información no disponible."
    )
    canvas.setFont("Helvetica", 7)
    page_width = letter[0]

    # 🔽 Ajuste: justo encima del pie de página
    canvas.drawCentredString(page_width / 2, 50, notas_texto)
    
    canvas.restoreState()

# **Función para el pie de página**
def agregar_pie_pagina(canvas, doc, factura):
    canvas.saveState()
    
    # 📌 Texto del proveedor
    proveedor_texto = "Proveedor Tecnológico: Teleinte SAS - NIT: 830.020.470-5 / Nombre del software: Afacturar.com www.afacturar.com"
    canvas.setFont("Helvetica", 6)
    
    # 📌 Mantener en la parte inferior centrado
    page_width = letter[0]
    text_y = 30  # Ajuste de altura para el texto
    canvas.drawCentredString(page_width / 2 - 40, text_y, proveedor_texto)  # Movemos un poco más a la izquierda
    
    # ✅ Agregar el logo desde Base64
    
    logo_base64 = factura.get("datos_documento", {}).get("logo", None)
    
    if logo_base64:
        try:
            # 🔹 Decodificar la imagen base64
            logo_data = base64.b64decode(logo_base64)
            logo_buffer = BytesIO(logo_data)
            logo_image = ImageReader(logo_buffer)

            # 🔹 Definir la posición del logo en el pie de página
            logo_width = 79  # Ajuste fino del tamaño
            logo_height = 20
            logo_x = page_width / 2 + 130  # Movemos un poco a la derecha para evitar solapamiento
            logo_y = text_y - 6  # Bajamos un poco el logo para mejor alineación

            # 🔹 Dibujar la imagen en el canvas
            canvas.drawImage(logo_image, logo_x, logo_y, width=logo_width, height=logo_height, mask='auto')

        except Exception as e:
            print(f"Error al cargar la imagen del logo: {e}")

    canvas.restoreState()

# **Funciones para manejar encabezado y pie de página correctamente**
def primera_pagina(canvas, doc, factura):
    agregar_direccion_contacto(canvas, doc, factura)
    agregar_autorretenedores(canvas, doc, factura)
    agregar_pie_pagina(canvas, doc, factura)

    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(colors.grey)
    canvas.translate(10, 200)  # Posición: X desde borde izq., Y desde abajo (ajustable)
    canvas.rotate(90)  # Rota para que el texto vaya de abajo hacia arriba
    canvas.drawString(0, 0, f"Fecha de validación DIAN: {factura['fecha_validacion_dian']}")
    canvas.restoreState()

def paginas_siguientes(canvas, doc, factura):
    agregar_direccion_contacto(canvas, doc, factura)
    agregar_autorretenedores(canvas, doc, factura)
    agregar_pie_pagina(canvas, doc, factura)

    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(colors.grey)
    canvas.translate(10, 200)  # Posición: X desde borde izq., Y desde abajo (ajustable)
    canvas.rotate(90)  # Rota para que el texto vaya de abajo hacia arriba
    canvas.drawString(0, 0, f"Fecha de validación DIAN: {factura['fecha_validacion_dian']}")
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
    
    styles = getSampleStyleSheet()
    elements = []

    # **Encabezado Principal**
    def agregar_encabezado():
        razon_social_style = ParagraphStyle(
            name="RazonSocialTitle",
            fontName="Helvetica-Bold",
            fontSize=16,
            alignment=1,
            spaceAfter=6
        )

        header_data = [
            [Paragraph(f"<b>{factura['datos_obligado']['razon_social']}</b>", razon_social_style)]
        ]
        header_table = Table(header_data, colWidths=[500])
        header_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 20))

        # **Información Fija (Izquierda) + QR (Centro) + Factura Electrónica (Derecha)**
        datos_obligado = factura.get("datos_obligado", {})
        info_fija = [
            f"NIT: {datos_obligado.get('documento_obligado', 'N/A')}",
            f"Actividad Económica: {datos_obligado.get('actividad_economica', 'N/A')}",
            f"Régimen: {datos_obligado.get('regimen', 'N/A')}",
            f"Responsable IVA: {datos_obligado.get('responsable_iva', 'N/A')}",
            f"Tarifa ICA: {datos_obligado.get('tarifa_ica', 'N/A')}"
        ]
        info_paragraphs = [Paragraph(f"<b>{line}</b>", styles["Normal"]) for line in info_fija]

        logo_ofe_b64 = factura.get("datos_obligado", {}).get("logo_ofe")
        logo_ofe_img = None
        if logo_ofe_b64:
            try:
                logo_data = base64.b64decode(logo_ofe_b64)
                logo_buffer = BytesIO(logo_data)
                logo_ofe_img = Image(logo_buffer, width=90, height=60)  # Ajusta el tamaño si lo deseas
            except Exception as e:
                print(f"⚠️ Error al cargar logo_ofe: {e}")

        qr_code = generar_qr(factura['qr'])
        qr_path = "temp_qr.png"
        with open(qr_path, "wb") as f:
            f.write(qr_code.getbuffer())

        qr_image = Image(qr_path, width=70, height=70)

        factura_info = Table([
            [Paragraph("<b>Factura electrónica de venta</b>", styles["Normal"])],
            [Paragraph(f"<b>{factura['encabezado']['prefijo']}{factura['encabezado']['id_factura']}</b>", styles["Normal"])]
        ], colWidths=[120])
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
        cliente_data = [
            [Paragraph("<b>Información del Cliente</b>", styles["Normal"]), "", "", ""]  # Título centrado en toda la tabla
        ]

        # Filas organizadas correctamente
        cliente_data += [
            ["Nombre:", factura["informacion_adquiriente"]["nombre"]["razon_social"],
            "Correo Electrónico:", factura["informacion_adquiriente"]["correo_electronico"]],
            
            ["NIT:", factura["informacion_adquiriente"]["identificacion"],
            "Teléfono:", factura["informacion_adquiriente"]["numero_movil"]],

            ["Dirección:", factura["informacion_adquiriente"]["direccion"],
            "Ciudad:", factura["informacion_adquiriente"]["ciudad"]],

            ["Departamento:", factura["informacion_adquiriente"]["departamento"],
            "País:", factura["informacion_adquiriente"]["pais"]],

            ["Moneda:", factura["encabezado"]["moneda"],
            "Método de pago:", factura["encabezado"]["metodo_de_pago"]],

            ["Tipo de pago:", factura["encabezado"]["tipo_de_pago"],
            "Condición de pago:", "Sin especificar"],

            ["Orden de Compra:", factura["encabezado"]["numero_orden"],
            "Tipo de pago:", factura["encabezado"]["tipo_de_pago"]],

            ["Fecha y Hora de expedición:", f"{factura['encabezado']['fecha']} {factura['encabezado']['hora']}",
            "Fecha de Vencimiento:", factura["encabezado"]["fecha_vencimiento"]],

            ["CUFE:", factura["cufe"], "", ""],
            ["", "", "", ""]
        ]

        # Crear la tabla con dimensiones homogéneas y anchos bien distribuidos
        cliente_table = Table(cliente_data, colWidths=[100, 180, 100, 180])
        cliente_table.setStyle(TableStyle([
            ('SPAN', (0, 0), (-1, 0)),  
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                                              
            ('BACKGROUND', (0, 0), (-1, 0), colors.gray),  
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                                                        
            ('GRID', (0, 1), (-1, -1), 1, colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('LEADING', (0, 0), (-1, -1), 8),  # Reduce el espacio vertical en las celdas
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),  # Reduce el padding inferior de cada celda
            ('TOPPADDING', (0, 0), (-1, -1), 0),  # Reduce el padding superior de cada celda
            ('BOX', (0, 0), (-1, -1), 1.5, colors.black),
        ]))
        elements.append(cliente_table)
        elements.append(Spacer(1, 10))

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
            ('BACKGROUND', (0, 0), (-1, 0), colors.gray),
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
        # **Definir un nuevo estilo de párrafo más pequeño**
        estilo_resolucion = ParagraphStyle(
            name="ResolucionTexto",
            fontName="Helvetica",
            fontSize=5,  # **Reducido a tamaño 5**
            leading=6,  # **Espaciado entre líneas más ajustado**
            alignment=0,  # **Alineación izquierda**
        )

        # Texto de la autorización de la numeración de facturación con el nuevo estilo
        texto_resolucion = Paragraph(
            factura["datos_adicionales"]["resolucion"], estilo_resolucion
        )

        totales_data = [
            [texto_resolucion, "Subtotal:", f"${float(factura['valor_factura']['valor_base']):,.2f}"],
            ["", "Descuento:", f"${float(factura['valor_factura']['valor_descuento_total']):,.2f}"],
            ["", "IVA:", f"${float(factura['valor_factura']['valor_total_impuesto_1']):,.2f}"],
            ["", "Anticipo:", f"${float(factura['valor_factura']['valor_anticipo']):,.2f}"],
            ["", "Total a Pagar:", f"${float(factura['valor_factura']['valor_total_a_pagar']):,.2f}"]
        ]

        # **Ajuste de anchos para mantener el total alineado**
        totales_table = Table(totales_data, colWidths=[280, 140, 140])  

        totales_table.setStyle(TableStyle([
            # **Borde negro exterior de la tabla**
            ('BOX', (0, 0), (-1, -1), 1.5, colors.black),

            # **Bordes internos blancos**
            ('GRID', (0, 0), (-1, -1), 1, colors.white),  

            # **Texto alineado a la derecha en la columna de valores**
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),

            # **Texto de la resolución: Centrado verticalmente y más pequeño**
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),

            ('SPAN', (0, 0), (0, -1)),

            ('VALIGN', (0, 0), (0, -1), 'MIDDLE'),  # **Centrado verticalmente**
            
            # **Texto negro en todas las celdas**
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),

            # **Fondo blanco en todas las celdas**
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),

            # **Eliminar padding extra para compactar la tabla**
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),  # **Aún más compacto**
            ('TOPPADDING', (0, 0), (-1, -1), 1),  # **Reduce espacio**
            ('FONTSIZE', (0, 0), (-1, -1), 7),  
        ]))

        elements.append(totales_table)
        elements.append(Spacer(1, 8))

    # **Datos Adicionales del Sector Salud**
    def agregar_sector_salud():
        # **Extraer la colección de información adicional**
        datos_salud = factura["datos_adicionales"]

        sector_data = [
            [Paragraph("<b>Datos Adicionales del Sector Salud</b>", styles["Normal"])],  # **Encabezado**
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

            ('BACKGROUND', (0, 0), (-1, 0), colors.gray),  # **Fondo gris para el título**
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

    max_altura_pagina = 300
    altura_actual = 100
    buffer_filas = []

    def agregar_tabla_detalle(buffer_filas):
        if not buffer_filas:
            return

        tabla = Table(
            [["#", "Descripción", "U. Med", "Cantidad", "Valor Unitario", "% Imp.", "Descuento", "Total"]] + buffer_filas,
            colWidths=[25, 180, 40, 40, 75, 50, 75, 75]
        )
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.gray),
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

    for i, detalle in enumerate(factura["detalle_factura"]):
        parrafo = Paragraph(detalle["descripcion"], descripcion_style)
        altura_parrafo = parrafo.wrap(180, 0)[1]  # ancho columna descripción
        altura_fila = max(altura_parrafo, 10) + 4  # padding

        if altura_actual + altura_fila > max_altura_pagina:
            agregar_tabla_detalle(buffer_filas)
            buffer_filas = []
            altura_actual = 0
            elements.append(PageBreak())
            agregar_encabezado()
            agregar_info_cliente()

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

    # Agregar últimos elementos + totales
    agregar_tabla_detalle(buffer_filas)
    agregar_totales()
    agregar_sector_salud()
    pdf.build(elements, onFirstPage=lambda canvas, doc: primera_pagina(canvas, doc, factura), 
              onLaterPages=lambda canvas, doc: paginas_siguientes(canvas, doc, factura),canvasmaker=NumberedCanvas)
    buffer.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"cufe_{factura['cufe']}_{timestamp}.pdf"

    # 🗓️ Obtener fecha actual
    fecha_actual = datetime.now()
    anio = str(fecha_actual.year)
    mes = f"{fecha_actual.month:02d}"
    dia = f"{fecha_actual.day:02d}"

    # 📂 NIT de la empresa
    nit = factura["datos_obligado"]["documento_obligado"]

    # 🛣️ Ruta dentro del bucket
    ruta_s3 = f"{nit}/{anio}/{mes}/{dia}/{pdf_filename}"

    s3_client.upload_fileobj(buffer, S3_BUCKET_NAME, ruta_s3)

    return f"{nit}/{anio}/{mes}/{dia}/{pdf_filename}"
