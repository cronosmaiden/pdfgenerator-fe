# Imagen base oficial de Python
FROM python:3.11-slim

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos de requerimientos
COPY requirements.txt .

# Instala las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código de la aplicación
COPY . .

# Expone el puerto de la app
EXPOSE 8000

# Comando para iniciar la app (ajusta si usas otro archivo)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
