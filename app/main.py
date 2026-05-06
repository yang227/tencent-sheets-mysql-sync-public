from contextlib import asynccontextmanager
from pathlib import Path
import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_config
from app.routers import config_router, mysql_browser_router, sync_router
from app.routers.enhanced_router import router as enhanced_router
from app.routers.monitoring_router import router as monitoring_router
from app.routers.mysql_config_router import router as mysql_config_router
from app.routers.tencent_config_router import router as tencent_config_router
from app.routers.tencent_helper import router as tencent_helper
from app.routers.workbench_router import router as workbench_router
from app.scheduler.sync_scheduler import SyncScheduler
from app.services.mysql_service import MySQLService, get_mysql_service
from app.webhooks.tencent_webhook import router as tencent_webhook

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"
LEGACY_STATIC_DIR = BASE_DIR / "app" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    SyncScheduler.init()
    yield
    SyncScheduler.shutdown()


def create_app() -> FastAPI:
    config = get_config()
    app_config = config.app

    app = FastAPI(
        title="Tencent Sheets MySQL Sync",
        description="Tencent Sheets and MySQL bidirectional sync platform",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(config_router)
    app.include_router(sync_router)
    app.include_router(mysql_browser_router)
    app.include_router(tencent_helper)
    app.include_router(enhanced_router)
    app.include_router(monitoring_router)
    app.include_router(mysql_config_router)
    app.include_router(tencent_config_router)
    app.include_router(workbench_router)
    app.include_router(tencent_webhook)

    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "service": "tencent-sheets-mysql-sync",
            "port": app_config.port,
        }

    @app.post("/init")
    async def init_system(db: MySQLService = Depends(get_mysql_service)):
        try:
            db.init_system_tables()
            return {"message": "系统表初始化完成"}
        except Exception as exc:
            logger.error("System initialization failed: %s", exc)
            raise HTTPException(status_code=500, detail=f"初始化失败: {exc}") from exc

    @app.get("/")
    async def root():
        if (FRONTEND_DIST_DIR / "index.html").exists():
            return FileResponse(FRONTEND_DIST_DIR / "index.html")
        return FileResponse(LEGACY_STATIC_DIR / "index.html")

    @app.get("/favicon.svg")
    async def frontend_favicon():
        if (FRONTEND_DIST_DIR / "favicon.svg").exists():
            return FileResponse(FRONTEND_DIST_DIR / "favicon.svg")
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/icons.svg")
    async def frontend_icons():
        if (FRONTEND_DIST_DIR / "icons.svg").exists():
            return FileResponse(FRONTEND_DIST_DIR / "icons.svg")
        raise HTTPException(status_code=404, detail="Not Found")

    if (FRONTEND_DIST_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="assets")

    return app


app = create_app()

app.mount("/static", StaticFiles(directory=LEGACY_STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    runtime_config = get_config()
    uvicorn.run(
        "app.main:app",
        host=runtime_config.app.host,
        port=runtime_config.app.port,
        reload=True,
    )
