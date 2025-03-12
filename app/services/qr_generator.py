import qrcode
from io import BytesIO

def generar_qr(data: str):
    qr = qrcode.make(data)
    qr_bytes = BytesIO()
    qr.save(qr_bytes, format="PNG")
    qr_bytes.seek(0)
    return qr_bytes
