from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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

# ⛑️ Manejador para errores de validación de datos (422 Unprocessable Entity)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"💥 Error de validación en {request.url.path}")
    logger.error(f"📄 Detalles: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": exc.body
        }
    )

# Incluir las rutas
app.include_router(auth_router)
app.include_router(pdf_router)

@app.get("/")
def root():
    logger.info("📌 Acceso a la raíz de la API")
    return {"message": "API de Generación de PDF con QR funcionando correctamente"}