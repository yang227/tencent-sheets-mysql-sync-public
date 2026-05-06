FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
COPY config.example.yaml ./config.example.yaml
COPY .env.example ./.env.example
COPY frontend/public ./frontend/public
COPY frontend/dist ./frontend/dist

EXPOSE 8083

CMD ["sh", "-c", "python scripts/docker_bootstrap.py && uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT:-8083}"]
