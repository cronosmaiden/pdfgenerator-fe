from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from app.logging_config import logger

async def http_exception_handler(request: Request, exc: HTTPException):
    """ Manejo de errores HTTP estándar """
    logger.warning(f"⚠️ HTTP {exc.status_code}: {exc.detail} en {request.method} {request.url}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

async def general_exception_handler(request: Request, exc: Exception):
    """ Manejo de excepciones no controladas """
    logger.critical(f"🔥 ERROR CRÍTICO en {request.method} {request.url}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Error interno del servidor"}
    )
