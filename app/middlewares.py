import time
import json
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.logging_config import logger

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        """ Middleware para registrar todas las peticiones y respuestas """
        start_time = time.time()
        body = None

        # Leer el cuerpo de la petición en métodos POST, PUT y PATCH
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
            try:
                body = json.loads(body.decode("utf-8"))  # Convertir a JSON si es posible
            except json.JSONDecodeError:
                body = str(body)  # Si no es JSON, guardarlo como string

        logger.info(f"📩 PETICIÓN: {request.method} {request.url} | Body: {body if body else 'No Body'}")

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            logger.info(
                f"✅ RESPUESTA: {response.status_code} {request.method} {request.url} "
                f"(⏳ {process_time:.2f}s)"
            )

            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"❌ ERROR: {request.method} {request.url} - {str(e)} "
                f"(⏳ {process_time:.2f}s)", exc_info=True
            )
            raise e
