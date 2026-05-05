from fastapi import FastAPI

from backend.api.manual_dispatch import router as manual_dispatch_router

app = FastAPI(title="Manual Dispatch Board API")
app.include_router(manual_dispatch_router)
