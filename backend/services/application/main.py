from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers.applications import router as applications_router


app = FastAPI(
    title="DATA 260 Lab 2 - Pair 03 Application Service",
    version="0.2.0",
)

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

app.include_router(applications_router)


@app.get("/")
def read_root():
    return {
        "message": "Pair 03 Application Service is running",
        "service": "application",
        "pair": "03",
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "application",
        "pair": "03",
    }
