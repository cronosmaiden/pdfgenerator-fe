#!/usr/bin/env python
# ─────────────────────────────────────────────────────────────
# etiqueta_png_base64.py
# Crea una etiqueta/factura con datos + QR, la guarda en disco
# (etiqueta.png) y muestra la cadena Base-64 correspondiente.
# Solo requiere Pillow y qrcode →  pip install pillow qrcode
# ─────────────────────────────────────────────────────────────

import io, base64, textwrap
from PIL import Image, ImageDraw, ImageFont
import qrcode

# ─── 1) DATOS QUE QUIERES MOSTRAR ────────────────────────────
data = {
    "NumFac"   : "CED57157",
    "FecFac"   : "2025-02-26",
    "HorFac"   : "15:25:25",
    "NitFac"   : "800231602",
    "DocAdq"   : "830103525",
    "ValFac"   : "111724500.00",
    "ValIva"   : "0.00",
    "ValOtroIm": "0.00",
    "ValTolFac": "111724500.00",
    "CUFE"     : "ce81aed7a299bf74aede1c8f8b0416bda4ce60593975266e22ff115bc5e26fdee1ca2a9045ed619516d5278191923409",
}
qr_url = (
    "https://catalogo-vpfe.dian.gov.co/document/searchqr?"
    f"documentkey={data['CUFE']}"
)

# ─── 2) PARÁMETROS DE DISEÑO ─────────────────────────────────
WIDTH, HEIGHT   = 600, 460           # tamaño de la etiqueta
MARGIN          = 20                 # margen izquierdo/superior
LINE_SPACING    = 32                 # salto entre líneas
QR_SIZE         = 140                # tamaño del QR
LABEL_FONT_SIZE = 22
VALUE_FONT_SIZE = 22

def load_font(size: int) -> ImageFont.FreeTypeFont:
    """Intenta cargar Arial; cae a la fuente por defecto si no existe."""
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()

font_label = load_font(LABEL_FONT_SIZE)
font_value = load_font(VALUE_FONT_SIZE)

# ─── 3) CREA EL LIENZO EN BLANCO Y EL QR ─────────────────────
canvas = Image.new("RGB", (WIDTH, HEIGHT), "white")
draw   = ImageDraw.Draw(canvas)

qr_img = qrcode.make(qr_url).resize((QR_SIZE, QR_SIZE))
canvas.paste(qr_img, (WIDTH - QR_SIZE - MARGIN, MARGIN))

# ─── 4) ESCRIBE LOS DATOS ────────────────────────────────────
x, y = MARGIN, MARGIN
for key, val in data.items():
    # Clave (etiqueta)
    draw.text((x, y), f"{key}:", font=font_label, fill="black")
    # Valor (si es CUFE, envolver texto largo)
    if key == "CUFE":
        wrapped = textwrap.fill(val, width=48)
        draw.multiline_text((x + 150, y), wrapped,
                            font=font_value, fill="black", spacing=4)
        y += LINE_SPACING * (wrapped.count("\n") + 1)
    else:
        draw.text((x + 150, y), val, font=font_value, fill="black")
        y += LINE_SPACING

# ─── 5) CONVIERTE A PNG → BASE-64 ───────────────────────────
buffer = io.BytesIO()
canvas.save(buffer, format="PNG")
png_bytes = buffer.getvalue()

b64_str = base64.b64encode(png_bytes).decode("utf-8")
data_uri = "data:image/png;base64," + b64_str

# ─── 6) RESULTADOS ───────────────────────────────────────────
with open("etiqueta.png", "wb") as f:
    f.write(png_bytes)

print("✅  Archivo 'etiqueta.png' creado.")
print("✅  Cadena Base-64 generada (primeros 120 caracteres):")
print(data_uri)
# Si quieres la cadena completa, usa print(data_uri)
