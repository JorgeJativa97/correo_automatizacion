FROM python:3.9-slim

# Instalar dependencias de sistema
RUN apt-get update && \
    apt-get install -y libaio1 wget unzip && \
    rm -rf /var/lib/apt/lists/*

# Descargar Oracle Instant Client Lite
WORKDIR /opt/oracle
RUN wget https://download.oracle.com/otn_software/linux/instantclient/instantclient-basiclite-linuxx64.zip -O client.zip && \
    unzip client.zip && \
    rm client.zip && \
    mv instantclient_* instantclient

# Configurar entorno Oracle
ENV LD_LIBRARY_PATH=/opt/oracle/instantclient:$LD_LIBRARY_PATH
ENV PATH="$PATH:/opt/oracle/instantclient"

# Copiar requirements primero para cachear
COPY requirements.txt .

# Instalar dependencias con reinstalación forzada de numpy
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --force-reinstall -r requirements.txt


# Copiar aplicación
COPY reporte_diario.py .

# Directorio de trabajo
WORKDIR /app

# Comando de ejecución
CMD ["python", "/reporte_diario.py"]

# Copiar aplicación
#COPY . /app

# Directorio de trabajo
#WORKDIR /app

# Comando de ejecución
#CMD ["python", "reporte_diario.py"]