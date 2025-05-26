FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Установим системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenslide0 \
    libopenslide-dev \
    openslide-tools \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN cat .dockerignore

CMD ["/usr/local/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "log_config.yaml"]

#RUN apt-get update && apt-get install -y \
#    build-essential \
#    cmake \
#    git \
#    libopenjp2-7-dev \
#    libjpeg-dev \
#    libexpat1-dev \
#    libxml2-dev \
#    && rm -rf /var/lib/apt/lists/*

#RUN pip install --no-cache-dir \
#    pydicom \
#    python-gdcm \
#    pylibjpeg \
#    pylibjpeg-libjpeg \
#    pylibjpeg-openjpeg
