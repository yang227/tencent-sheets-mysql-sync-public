ARG APP_BASE_IMAGE=mysql:8.0
FROM ${APP_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN python3 -m ensurepip --upgrade \
    && python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python3 -m pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
COPY config.example.yaml ./config.example.yaml
COPY .env.example ./.env.example
COPY frontend/public ./frontend/public
COPY frontend/dist ./frontend/dist

ENTRYPOINT []
EXPOSE 8083

CMD ["sh", "-c", "python3 scripts/docker_bootstrap.py && python3 -m uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT:-8083}"]
