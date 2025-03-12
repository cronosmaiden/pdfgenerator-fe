import boto3
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from app.services.qr_generator import generar_qr
from io import BytesIO
import os

# Configuración de S3
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION")

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=S3_REGION
)

def generar_pdf(factura):
    # Mantener los márgenes correctos
    PAGE_WIDTH, PAGE_HEIGHT = letter
    MARGIN_X = 100  # Márgenes laterales
    MARGIN_Y = 85  # Márgenes superior e inferior
    CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN_X
    CONTENT_HEIGHT = PAGE_HEIGHT - 2 * MARGIN_Y

    pdf_path = "factura_generada.pdf"
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    # Obtener la ruta absoluta de la carpeta 'img'
    img_dir = os.path.join(os.path.dirname(__file__), "img")

    # Rutas de las imágenes dentro de services/img/
    img_minsalud = os.path.join(img_dir, "minsalud.jpeg")
    img_afacturar = os.path.join(img_dir, "afacturar.jpeg")
    img_checkok = os.path.join(img_dir, "checkok.jpeg")

    # Dibujar imágenes en la parte superior
    if os.path.exists(img_minsalud):
        c.drawImage(ImageReader(img_minsalud), MARGIN_X, PAGE_HEIGHT - 120, width=120, height=100, preserveAspectRatio=True)
    if os.path.exists(img_afacturar):
        c.drawImage(ImageReader(img_afacturar), PAGE_WIDTH - MARGIN_X - 200, PAGE_HEIGHT - 120, width=200, height=50, preserveAspectRatio=True)

    # Generar código QR y guardarlo temporalmente
    qr_code = generar_qr(factura.codigoUnicoValidacion)
    qr_path = "temp_qr.png"
    with open(qr_path, "wb") as f:
        f.write(qr_code.getbuffer())

    # Posición del QR en el centro con más espacio debajo (~2 cm)
    qr_size = 120
    qr_x = PAGE_WIDTH / 2 - qr_size / 2
    qr_y = PAGE_HEIGHT / 2 + 100  # Más separación con el texto

    c.drawImage(qr_path, qr_x, qr_y, width=qr_size, height=qr_size)

    # Título centrado
    c.setFont("Helvetica-Bold", 16)
    title = "Factura Electrónica"
    text_width = c.stringWidth(title, "Helvetica-Bold", 16)
    c.drawString(PAGE_WIDTH / 2 - text_width / 2, qr_y + 140, title)

    # Posición del contenido del texto con más espacio entre QR y texto (~2 cm)
    text_x = MARGIN_X
    text_y = qr_y - 90  # Espaciado mayor del QR al texto

    # Definir estilo de texto
    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]

    # Contenido de la factura con margen más amplio
    contenido = f"""
    <b>Proceso ID:</b> {factura.procesoId}<br/>
    <b>Estado:</b> {"Válido" if factura.esValido else "Inválido"}<br/>
    <b>Código Único:</b> {factura.codigoUnicoValidacion}<br/>
    <b>Fecha Validación:</b> {factura.fechaValidacion}<br/>
    <b>Documento Obligado:</b> {factura.numDocumentoIdObligado}<br/>
    <b>Número Documento:</b> {factura.numeroDocumento}<br/>
    <b>Fecha Emisión:</b> {factura.fechaEmision}<br/>
    <b>Total Factura:</b> ${factura.totalFactura}<br/>
    <b>Cantidad Usuarios:</b> {factura.cantidadUsuarios}<br/>
    <b>Cantidad Atenciones:</b> {factura.cantidadAtenciones}<br/>
    <b>Total Valor Servicios:</b> ${factura.totalValorServicios}<br/>
    <b>Identificación Adquiriente:</b> {factura.identificacionAdquiriente}<br/>
    <b>Código Prestador:</b> {factura.codigoPrestador}<br/>
    <b>Modalidad de Pago:</b> {factura.modalidadPago}<br/>
    """

    # Crear un párrafo con formato
    paragraph = Paragraph(contenido, normal_style)

    frame_y = MARGIN_Y + 200
    paragraph.wrapOn(c, CONTENT_WIDTH, frame_y)
    paragraph.drawOn(c, text_x, frame_y)

    
    if os.path.exists(img_checkok):
        check_size = qr_size  # Mismo tamaño que el QR (120px)
        check_x = PAGE_WIDTH / 2 - check_size / 2
        check_y = MARGIN_Y + 80  # MÁS ABAJO en la página para dejar espacio al texto
        c.drawImage(ImageReader(img_checkok), check_x, check_y, width=check_size, height=check_size, preserveAspectRatio=True)

    c.setFont("Helvetica", 10)  # Tamaño más pequeño

    footer_text1 = "Comprobante de Recepción y Validación SISPRO"
    footer_text2 = "Validación exitosa!!"
    
    # **Texto con URL clickable**
    footer_text3 = 'Procesado por Teleinte SAS con <u><a href="https://afacturar.com" color="blue">Afacturar.com</a></u>'

    # Posición del texto final
    footer_y = check_y - 60  # Colocarlo bien debajo del icono

    c.drawCentredString(PAGE_WIDTH / 2, footer_y, footer_text1)
    c.drawCentredString(PAGE_WIDTH / 2, footer_y - 15, footer_text2)

    # Dibujar el texto con la URL como un párrafo HTML para enlace clickable
    footer_paragraph = Paragraph(footer_text3, styles["Normal"])
    footer_paragraph.wrapOn(c, CONTENT_WIDTH, footer_y - 30)
    footer_paragraph.drawOn(c, PAGE_WIDTH / 2 - 53, footer_y - 30)  # Centramos manualmente

    # Guardar el PDF
    c.showPage()
    c.save()

    # Guardar el buffer en un archivo temporal
    buffer.seek(0)

    # **Generar nombre único del archivo**
    codigo_unico = factura.codigoUnicoValidacion[-50:]  # Últimos 50 caracteres
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Fecha y hora
    pdf_filename = f"factura_{codigo_unico}_{timestamp}.pdf"

    # **Subir el archivo a S3**
    s3_client.upload_fileobj(buffer, S3_BUCKET_NAME, pdf_filename)

    # **Eliminar el QR temporal**
    os.remove(qr_path)

    # **Retornar el nombre del archivo**
    return pdf_filename
