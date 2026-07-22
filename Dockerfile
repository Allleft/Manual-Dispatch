FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MANUAL_DISPATCH_HOST=0.0.0.0
ENV MANUAL_DISPATCH_PORT=8130
ENV MANUAL_DISPATCH_DB_PATH=/app/data/manual_dispatch.sqlite3
ENV MANUAL_DISPATCH_LOGBOOK_DIR=/app/data/logbook
ENV MANUAL_DISPATCH_ALLOW_REGISTRATION=false
ENV MANUAL_DISPATCH_SEED_DEMO_DATA=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY tools ./tools
COPY docs ./docs
COPY README.md ./

RUN mkdir -p /app/data /app/backups

EXPOSE 8130

CMD ["python", "-c", "import os, uvicorn; uvicorn.run('backend.main:app', host=os.environ.get('MANUAL_DISPATCH_HOST', '0.0.0.0'), port=int(os.environ.get('MANUAL_DISPATCH_PORT', '8130')))"]
