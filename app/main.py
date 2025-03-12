from fastapi import FastAPI, HTTPException
from app.routes.auth_routes import router as auth_router
from app.routes.routes import router as pdf_router
from app.middlewares import LoggingMiddleware
from app.exception_handler import http_exception_handler, general_exception_handler
from app.logging_config import logger

app = FastAPI(title="API para Generación de PDF con QR")

# Agregar Middleware de Logging
app.add_middleware(LoggingMiddleware)

# Manejo de errores globales
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Incluir las rutas
app.include_router(auth_router)
app.include_router(pdf_router)

@app.get("/")
def root():
    logger.info("📌 Acceso a la raíz de la API")
    return {"message": "API de Generación de PDF con QR funcionando correctamente"}
