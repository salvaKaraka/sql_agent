# Imagen base oficial de Python
FROM python:3.11-slim

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Instala dependencias del sistema si es necesario
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia los archivos
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Expone el puerto en el que corre FastAPI (por defecto 8000)
EXPOSE 8000

# Comando para iniciar FastAPI con Uvicorn
CMD ["uvicorn", "app:app","--host","0.0.0.0","--reload"]
