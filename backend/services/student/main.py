from fastapi import FastAPI

from backend.common.runtime import configure_threadpool
from fastapi.middleware.cors import CORSMiddleware

from backend.common.tracing import TraceMiddleware
from backend.app.routers.student_auth import router as student_auth_router


app = FastAPI(
    title="DATA 260 Lab 2 - Pair 03 Student Service",
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

app.add_middleware(TraceMiddleware, service="student")

app.include_router(student_auth_router)


@app.get("/")
def read_root():
    return {
        "message": "Pair 03 Student Service is running",
        "service": "student",
        "pair": "03",
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "student",
        "pair": "03",
    }
