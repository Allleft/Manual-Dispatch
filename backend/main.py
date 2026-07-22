from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.api.manual_dispatch import router as manual_dispatch_router
from backend.api.manual_dispatch_routes.common import is_env_flag_enabled

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
ENABLE_API_DOCS_ENV = "MANUAL_DISPATCH_ENABLE_API_DOCS"


class NoStoreStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


def create_app():
    docs_enabled = is_env_flag_enabled(ENABLE_API_DOCS_ENV, default=False)
    app = FastAPI(
        title="Manual Dispatch Board API",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.include_router(manual_dispatch_router)
    app.mount(
        "/frontend",
        NoStoreStaticFiles(directory=FRONTEND_DIR, html=True),
        name="frontend",
    )

    @app.get("/", include_in_schema=False)
    def redirect_to_frontend():
        return RedirectResponse(url="/frontend/")

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    return app


app = create_app()
