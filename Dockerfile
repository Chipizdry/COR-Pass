FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenslide0 \
    libopenslide-dev \
    openslide-tools \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Установка системных зависимостей для GDCM и DICOM
RUN apt-get update && \
    apt-get install -y \
    libgdcm-tools \
    libgdcm3.0 \
    libjpeg-dev \
    libopenjp2-7-dev \
    && rm -rf /var/lib/apt/lists/*

# Установка Python зависимостей
RUN pip install --upgrade pip && \
    pip install \
    pydicom \
    gdcm \
    pylibjpeg \
    pylibjpeg-libjpeg \
    pylibjpeg-openjpeg    

COPY . /app



CMD ["/usr/local/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "log_config.yaml"]


