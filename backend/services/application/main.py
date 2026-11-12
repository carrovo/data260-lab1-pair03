from fastapi import FastAPI

from backend.common.runtime import configure_threadpool
from fastapi.middleware.cors import CORSMiddleware

from backend.common.tracing import TraceMiddleware
from backend.app.routers.applications import router as applications_router


app = FastAPI(
    title="DATA 260 Lab 2 - Pair 03 Application Service",
    version="0.2.0",
)

configure_threadpool(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TraceMiddleware, service="application")

app.include_router(applications_router)


@app.get("/")
def read_root():
    return {
        "message": "Pair 03 Application Service is running",
        "service": "application",
        "pair": "03",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "application",
        "pair": "03",
    }
