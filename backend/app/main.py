from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

from backend.common.runtime import configure_threadpool
from backend.common.tracing import TraceMiddleware
from backend.app.routers.assistant import router as assistant_router
from backend.app.routers.applications import router as applications_router
from backend.app.routers.company_applications import (
    router as company_applications_router,
)
from backend.app.routers.company_auth import router as company_auth_router
from backend.app.routers.company_events import router as company_events_router
from backend.app.routers.company_jobs import router as company_jobs_router
from backend.app.routers.company_profile import router as company_profile_router
from backend.app.routers.events import router as events_router
from backend.app.routers.registration_routes import (
    router as registration_router,
)
from backend.app.routers.jobs import router as jobs_router
from backend.app.routers.student_auth import router as student_auth_router
from backend.app.routers.students_search import router as students_search_router

app = FastAPI(
    title="DATA 260 Lab 1 — Pair 03",
    version="0.1.0",
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

app.add_middleware(TraceMiddleware, service="app")

app.include_router(student_auth_router)
app.include_router(jobs_router)
app.include_router(applications_router)
app.include_router(events_router)
app.include_router(registration_router)
app.include_router(assistant_router)
app.include_router(company_auth_router)
app.include_router(company_profile_router)
app.include_router(company_jobs_router)
app.include_router(company_applications_router)
app.include_router(company_events_router)
app.include_router(students_search_router)

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
