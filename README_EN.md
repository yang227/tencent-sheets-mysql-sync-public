# Tencent Sheets – MySQL Sync Platform

A bidirectional synchronization platform between [Tencent Docs](https://docs.qq.com/) online spreadsheets and MySQL, designed for enterprise internal use.

- **FastAPI** backend API
- **Vue 3** frontend workbench
- MySQL metadata store
- Startup scripts for Linux / macOS / Windows
- Docker one-click build & deploy

---

## 1. Project Goals

This project provides the following capabilities:

- Read headers and data from Tencent Docs online spreadsheets
- Read MySQL table structures and field metadata
- Map spreadsheet columns to database columns directly
- Execute sheet-to-MySQL writes and MySQL-to-sheet writebacks on schedule or on demand
- Configure, map, trigger, and verify everything through a web-based frontend

## 2. Configuration Principles

All runtime parameters are injected through config files or environment variables — nothing is hard-coded in business logic.

**Application runtime config** — `config.yaml`:

- `database.*`
- `app.*`
- `frontend.*`
- `tencent.*`
- `sync.*`

**Container & deployment config** — `.env`:

- `APP_CONTAINER_NAME`, `APP_BASE_IMAGE`
- `DATABASE_*`
- `METADATA_MYSQL_*`
- `TENCENT_*`
- `ENCRYPTION_KEY`

**Example files provided:**

- `.env.example`
- `config.example.yaml`

## 3. Prerequisites

### Local script mode

- Python 3.10+
- Node.js 20+ (frontend dev only)
- An accessible MySQL instance

### Docker mode

- Docker & Docker Compose installed
- Local `mysql:8.0` image available

> The Docker setup builds the application image directly on top of `mysql:8.0`. It does **not** pull separate `python` or `node` base images. Frontend static assets are served from the committed `frontend/dist` directory.

## 4. Local Startup

### 4.1 Bootstrap

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_local.ps1
```

Linux / macOS:

```bash
chmod +x scripts/*.sh
./scripts/bootstrap_local.sh
```

### 4.2 Start metadata database

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_metadata_mysql.ps1
```

Linux / macOS:

```bash
./scripts/start_metadata_mysql.sh
```

### 4.3 Start backend

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_backend.ps1
```

Linux / macOS:

```bash
./scripts/start_backend.sh
```

### 4.4 Start frontend dev server

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_frontend.ps1
```

Linux / macOS:

```bash
./scripts/start_frontend.sh
```

### 4.5 One-command full stack

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_local_stack.ps1
```

Linux / macOS:

```bash
./scripts/run_local_stack.sh
```

## 5. Docker One-Click Deploy

### 5.1 Initialize config

```powershell
Copy-Item .env.example .env
```

Fill in the following values for your environment:

- `DATABASE_PASSWORD`
- `TENCENT_APP_ID`
- `TENCENT_OPEN_ID`
- `TENCENT_DOCS_ACCESS_TOKEN`
- `ENCRYPTION_KEY`

If your local MySQL image is not `mysql:8.0`, override:

- `APP_BASE_IMAGE`
- `METADATA_MYSQL_IMAGE`

### 5.2 Start

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\docker_up.ps1
```

Linux / macOS:

```bash
chmod +x scripts/*.sh
./scripts/docker_up.sh
```

Equivalent:

```bash
docker compose up -d --build
```

### 5.3 Stop

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\docker_down.ps1
```

Linux / macOS:

```bash
./scripts/docker_down.sh
```

Equivalent:

```bash
docker compose down
```

## 6. Docker Startup Sequence

`docker-compose.yml` launches two services:

- `metadata-mysql`
- `app`

On startup the app container automatically:

1. Waits for MySQL to become healthy
2. Runs `migrations/init.sql`
3. Runs `migrations/add_config_tables.sql`
4. Starts `uvicorn`

Related files:

- `Dockerfile`
- `docker-compose.yml`
- `scripts/docker_bootstrap.py`

## 7. Access URLs

| Purpose        | URL                                |
|----------------|------------------------------------|
| Health check   | `http://127.0.0.1:8083/health`     |
| Swagger docs   | `http://127.0.0.1:8083/docs`       |
| All-in-one UI  | `http://127.0.0.1:8083/`           |
| Frontend dev   | `http://127.0.0.1:5173/`           |

## 8. Key Directories

| Directory      | Description                           |
|----------------|---------------------------------------|
| `app/`         | Backend application (FastAPI)         |
| `frontend/`    | Frontend app & built static assets    |
| `migrations/`  | Database init & migration scripts     |
| `scripts/`     | Startup, deploy, and utility scripts  |
| `tests/`       | Automated tests                       |

## 9. Release Variants

Three GitHub repository variants are maintained:

| Variant   | Repository                                              | Contents                                           |
|-----------|---------------------------------------------------------|----------------------------------------------------|
| Private   | `yang227/tencent-sheets-mysql-sync-private`             | Full project including memory & internal docs       |
| Public    | `yang227/tencent-sheets-mysql-sync-public`              | Public release without sensitive configs or memory  |
| GitHub    | `yang227/tencent-sheets-mysql-sync-github`              | Minimal set of files for public distribution        |

Generate all variants:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\create_project_variants.ps1
```

## License

This project is provided as-is for internal enterprise use. See repository settings for license details.