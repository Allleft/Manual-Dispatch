from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.api.manual_dispatch import router as manual_dispatch_router

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"


class NoStoreStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


app = FastAPI(title="Manual Dispatch Board API")
app.include_router(manual_dispatch_router)
app.mount("/frontend", NoStoreStaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.get("/", include_in_schema=False)
def redirect_to_frontend():
    return RedirectResponse(url="/frontend/")


@app.get("/health")
def health_check():
    return {"status": "ok"}
