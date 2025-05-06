FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

RUN cat .dockerignore

CMD ["/usr/local/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "log_config.yaml"]

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgdcm-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*