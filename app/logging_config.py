import logging
import os
from logging.handlers import RotatingFileHandler

# Crear directorio de logs si no existe
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Configuración de logs
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# Configurar el formato del log
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Configurar el logger principal para capturar todo (nivel DEBUG)
logging.basicConfig(
    level=logging.DEBUG,  # Capturamos todas las peticiones, pero luego limitaremos pdfminer
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3),
        logging.StreamHandler()
    ]
)

# Crear el logger de la aplicación
logger = logging.getLogger("fastapi_app")

# ─── Aquí bajamos el nivel de pdfminer para que sólo muestre WARNING/ERROR ───
logging.getLogger("pdfminer").setLevel(logging.WARNING)
logging.getLogger("pdfminer.pdfinterp").setLevel(logging.WARNING)
logging.getLogger("pdfminer.psparser").setLevel(logging.WARNING)
