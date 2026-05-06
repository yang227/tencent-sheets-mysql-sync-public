import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_config


def normalize_url_host(host: str) -> str:
    return "127.0.0.1" if host in {"0.0.0.0", "::"} else host


def main() -> None:
    config = get_config()

    app_host = config.app.host
    app_port = config.app.port
    frontend_host = config.frontend.host
    frontend_port = config.frontend.port

    backend_url = config.frontend.backend_url or f"http://{normalize_url_host(app_host)}:{app_port}"

    runtime = {
        "app_host": app_host,
        "app_port": app_port,
        "app_url_host": normalize_url_host(app_host),
        "frontend_host": frontend_host,
        "frontend_port": frontend_port,
        "frontend_url_host": normalize_url_host(frontend_host),
        "frontend_backend_url": backend_url,
        "metadata_compose_file": os.environ.get("METADATA_DOCKER_COMPOSE_FILE", "docker-compose.metadata.yml"),
        "metadata_container_name": os.environ.get("METADATA_MYSQL_CONTAINER_NAME", "tencent-sync-metadata-mysql"),
        "metadata_image": os.environ.get("METADATA_MYSQL_IMAGE", "mysql:8.0"),
        "metadata_port": int(os.environ.get("METADATA_MYSQL_PORT", str(config.database.port))),
        "metadata_host": os.environ.get("METADATA_MYSQL_HOST", config.database.host),
        "metadata_database": os.environ.get("METADATA_MYSQL_DATABASE", config.database.name),
        "metadata_root_user": os.environ.get("METADATA_MYSQL_ROOT_USER", "root"),
        "metadata_ready_timeout": int(os.environ.get("METADATA_MYSQL_READY_TIMEOUT", "60")),
    }

    print(json.dumps(runtime))


if __name__ == "__main__":
    main()
