from fastapi import FastAPI
from backend.app.routers.student_auth import router as student_auth_router

app = FastAPI(
    title="DATA 260 Lab 1 — Pair 03",
    version="0.1.0",
)

app.include_router(student_auth_router)

@app.get("/")
def read_root():
    return {
        "message": "DATA 260 Lab 1 API is running",
        "pair": "03",
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "pair": "03",
    }