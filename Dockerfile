FROM python:3.12-slim-bookworm

# Impress renders PPTX on the server; common metric-compatible fonts preserve layout.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-impress libreoffice-writer libgl1 libglib2.0-0 fonts-dejavu-core fonts-liberation fonts-crosextra-carlito \
    fonts-crosextra-caladea && rm -rf /var/lib/apt/lists/*
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --force-reinstall --no-deps --no-cache-dir opencv-python-headless==4.14.0.94
COPY . .
CMD ["sh", "-c", "exec gunicorn web_app:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --timeout 120"]
