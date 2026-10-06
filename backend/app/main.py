from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from backend.app.routers.student_auth import router as student_auth_router
from backend.app.routers.jobs import router as jobs_router

app = FastAPI(
    title="DATA 260 Lab 1 — Pair 03",
    version="0.1.0",
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

app.include_router(student_auth_router)
app.include_router(jobs_router)

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