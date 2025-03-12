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
    level=logging.DEBUG,  # Asegura que capturamos TODAS las peticiones
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3),  # Máximo 5MB por archivo, 3 copias
        logging.StreamHandler()  # También mostrar logs en la consola
    ]
)

# Crear el logger de la aplicación
logger = logging.getLogger("fastapi_app")
