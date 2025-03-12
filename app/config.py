import os

class Config:
    PDF_OUTPUT_PATH = os.getenv("PDF_OUTPUT_PATH", "temp_pdfs/")
    QR_TEMP_PATH = os.getenv("QR_TEMP_PATH", "temp_qr/")
    APP_NAME = "API Generación de PDF con QR"
    VERSION = "1.0.0"
    DATABASE_URL = "sqlite:///facturas.db"
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecreto")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Crear directorios si no existen
os.makedirs(Config.PDF_OUTPUT_PATH, exist_ok=True)
os.makedirs(Config.QR_TEMP_PATH, exist_ok=True)
